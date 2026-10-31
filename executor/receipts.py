"""Receipt engine: hash the evidence, sign the receipt with Ed25519.

A valid signature proves the receipt was not changed after we issued it. It
does not prove the portal accepted the application: say "tamper-evident
record", not "government-verified receipt".
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import settings
from .models import Receipt


def _load_or_create_key() -> Ed25519PrivateKey:
    path = settings.data_dir / "receipt_signing_key.pem"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)  # type: ignore[return-value]
    settings.ensure_dirs()
    key = Ed25519PrivateKey.generate()
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    path.chmod(0o600)
    return key


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(receipt: Receipt) -> bytes:
    body = receipt.model_dump(mode="json", exclude={"signature"})
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class Signer:
    def __init__(self):
        self._key = _load_or_create_key()
        pub = self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.public_key_b64 = base64.b64encode(pub).decode()
        self.key_id = hashlib.sha256(pub).hexdigest()[:16]

    def sign(self, receipt: Receipt) -> Receipt:
        receipt.signer_key_id = self.key_id
        receipt.signature = base64.b64encode(self._key.sign(canonical(receipt))).decode()
        return receipt

    def public_pem(self) -> str:
        return (
            self._key.public_key()
            .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            .decode()
        )


def verify(receipt: Receipt, public_key_b64: str) -> bool:
    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    try:
        pub.verify(base64.b64decode(receipt.signature), canonical(receipt))
        return True
    except (InvalidSignature, ValueError):
        return False
