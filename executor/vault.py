"""Profile vault: encrypted sensitive fields, resolved in memory at fill time only.

The model and every log see placeholders such as {{vault.mobile}}. The runner
swaps in the real value right before Playwright types it, and `redact()` scrubs
any value that leaks back through page text before it reaches an event.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken

from .config import settings
from .db import Store

PLACEHOLDER = re.compile(r"\{\{\s*(input|vault|portal|doc)\.([a-zA-Z0-9_]+)\s*\}\}")


def _load_key() -> bytes:
    if settings.vault_key:
        return settings.vault_key.encode()
    key_path = settings.data_dir / "vault.key"
    if key_path.exists():
        return key_path.read_bytes()
    settings.ensure_dirs()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    return key


class VaultError(Exception):
    pass


class Vault:
    def __init__(self, store: Store):
        self._store = store
        self._fernet = Fernet(_load_key())

    def put(self, fields: dict[str, str], ttl_s: int | None = None) -> str:
        if any("aadhaar" in k.lower() for k in fields):
            raise VaultError("Aadhaar numbers are never stored")
        ref = "vault_" + secrets.token_urlsafe(12)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_s or settings.vault_ttl_s)
        blob = self._fernet.encrypt(json.dumps({k: str(v) for k, v in fields.items()}).encode())
        self._store.put_vault(ref, blob, expires.isoformat())
        return ref

    def open(self, ref: str) -> "VaultSession":
        row = self._store.get_vault(ref)
        if not row:
            raise VaultError(f"unknown or expired vault_ref {ref}")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            self._store.delete_vault(ref)
            raise VaultError(f"vault_ref {ref} has expired")
        try:
            data = json.loads(self._fernet.decrypt(row["ciphertext"]))
        except InvalidToken as e:
            raise VaultError("vault entry cannot be decrypted with the current key") from e
        return VaultSession(ref, data)

    def keys(self, ref: str) -> set[str]:
        return set(self.open(ref)._data)

    def delete(self, ref: str) -> None:
        self._store.delete_vault(ref)


class VaultSession:
    """Decrypted values for one task, kept in memory only. Logs key use, never values."""

    def __init__(self, ref: str, data: dict[str, str]):
        self.ref = ref
        self._data = data
        self.access_log: list[dict[str, str]] = []

    def has(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, step_id: str) -> str:
        if key not in self._data:
            raise VaultError(f"vault has no key '{key}'")
        self.access_log.append({"step_id": step_id, "key": key})
        return self._data[key]

    def redact(self, text: str) -> str:
        for value in self._data.values():
            if value and len(value) >= 4 and value in text:
                text = text.replace(value, mask(value))
        return text

    def sensitive_values(self) -> list[str]:
        return [v for v in self._data.values() if v]


class EmptyVault(VaultSession):
    def __init__(self):
        super().__init__("none", {})


def mask(value: str) -> str:
    value = str(value)
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]
