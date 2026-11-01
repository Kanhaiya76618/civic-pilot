# Skill Note: Cryptographic Receipts (Ed25519) & Hash-Chained Audit Ledger

## Overview & Architecture
To guarantee public transparency without relying on unverified claims, Swayam-sevak implements two layers of cryptographic integrity:
1. **Ed25519 Signed Execution Receipts**: Every portal submission generates a receipt signed by the agent's private key. Anyone can verify using the public key that the registration number, screenshot SHA-256 hash, and timestamp have not been tampered with.
2. **Hash-Chained Grievance Ledger**: Each ticket in the ledger contains a cryptographic hash of its canonical content plus the previous block's hash:
   $$\text{Block}_n = \text{SHA-256}(\text{CanonicalJSON}(\text{Payload}_n) \parallel \text{Hash}_{n-1})$$
   This makes historical grievance logs demonstrably tamper-evident.

---

## 1. Patterns
- **Asymmetric Ed25519 Signatures**: Use `nacl.signing.SigningKey` (Ed25519). Public keys are exposed at `/v1/receipts/public-key`.
- **SHA-256 Evidence Hashing**: Hash all submission artifacts (final screenshot, confirmation HTML, acknowledgment PDF). Include hashes in the receipt payload.
- **Canonical JSON Serialization**: Guarantee identical byte encoding before hashing by sorting keys (`sort_keys=True`) and stripping whitespace (`separators=(',', ':')`).
- **Verifiable Receipt API**: The verification endpoint `POST /v1/receipts/verify` accepts the receipt and checks `VerifyKey.verify(message, signature)` without needing database access.

---

## 2. Common Pitfalls
1. **JSON Serialization Non-Determinism**: Standard `json.dumps()` may produce differing key orders or whitespace formatting across Python versions or languages, invalidating signature checks. Always use deterministic canonical formatting.
2. **Exposing the Private Key**: Private signing keys must be loaded from protected files or environment variables with strict permissions (`chmod 600`), never committed to git or printed in logs.
3. **Confusing Receipt Meaning**: A valid signature proves the *agent's audit log* is authentic and unaltered; it does not guarantee the external government portal will resolve the grievance quickly.

---

## 3. Minimal Working Code Skeleton

```python
import base64
import hashlib
import json
from nacl.signing import SigningKey, VerifyKey

def canonical_bytes(payload: dict) -> bytes:
    """Produces deterministic byte representation for hashing and signing."""
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')

class ReceiptSigner:
    def __init__(self, seed: bytes = None):
        self.signing_key = SigningKey(seed) if seed else SigningKey.generate()
        self.verify_key = self.signing_key.verify_key
        self.key_id = hashlib.sha256(self.verify_key.encode()).hexdigest()[:16]

    def sign_receipt(self, receipt_data: dict) -> dict:
        msg = canonical_bytes(receipt_data)
        signed = self.signing_key.sign(msg)
        return {
            **receipt_data,
            "signer_key_id": self.key_id,
            "signature": base64.b64encode(signed.signature).decode('ascii')
        }

    @staticmethod
    def verify_receipt(receipt: dict, public_key_b64: str) -> bool:
        try:
            vk = VerifyKey(base64.b64decode(public_key_b64))
            sig = base64.b64decode(receipt["signature"])
            data_to_verify = {k: v for k, v in receipt.items() if k not in ("signature", "signer_key_id")}
            msg = canonical_bytes(data_to_verify)
            vk.verify(msg, sig)
            return True
        except Exception:
            return False

class HashChainedLedger:
    def __init__(self):
        self.chain = []
        self.last_hash = "0" * 64 # Genesis hash

    def append_ticket(self, ticket_payload: dict) -> dict:
        block_data = {
            "index": len(self.chain),
            "prev_hash": self.last_hash,
            "ticket": ticket_payload
        }
        block_hash = hashlib.sha256(canonical_bytes(block_data)).hexdigest()
        block_data["ticket_hash"] = block_hash
        self.chain.append(block_data)
        self.last_hash = block_hash
        return block_data
```

---

## 4. Verified Source Links
- PyNaCl (Python binding to libsodium) Documentation: https://pynacl.readthedocs.io/
- RFC 8032 — Edwards-Curve Digital Signature Algorithm (EdDSA): https://datatracker.ietf.org/doc/html/rfc8032
- Canonical JSON Specification: https://gibson042.github.io/canonicaljson-spec/
