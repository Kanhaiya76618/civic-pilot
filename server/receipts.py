"""
Swayam-sevak Receipt Signing & Hash-Chained Verifiable Ledger
Uses PyNaCl (Ed25519) for tamper-evident digital signatures and SHA-256 hash chaining.
"""

import os
import json
import hashlib
from typing import Dict, Any, Tuple, Optional
import nacl.signing
import nacl.encoding

# Key management: Load or generate a persistent Ed25519 key for Swayam-sevak authority
KEY_DIR = os.path.join(".data", "keys")
KEY_PATH = os.path.join(KEY_DIR, "authority_ed25519.key")

def get_or_create_signing_key() -> nacl.signing.SigningKey:
    """Retrieves or creates a persistent Ed25519 signing key."""
    os.makedirs(KEY_DIR, exist_ok=True)
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            seed = f.read()
        return nacl.signing.SigningKey(seed)
    else:
        key = nacl.signing.SigningKey.generate()
        with open(KEY_PATH, "wb") as f:
            f.write(key.encode())
        return key


def get_public_key_hex() -> str:
    """Returns the hex-encoded Ed25519 public key of the Swayam-sevak authority."""
    signing_key = get_or_create_signing_key()
    return signing_key.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")


def canonical_json(data: Dict[str, Any]) -> str:
    """Produces deterministic, canonically-ordered JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def compute_ticket_hash(payload: Dict[str, Any], prev_hash: str) -> str:
    """
    Computes SHA-256 ticket hash:
    ticket_hash = SHA256( canonical_json(payload) + prev_hash )
    """
    canonical_str = canonical_json(payload)
    hasher = hashlib.sha256()
    hasher.update(canonical_str.encode("utf-8"))
    hasher.update(prev_hash.encode("utf-8"))
    return hasher.hexdigest()


def sign_receipt(payload: Dict[str, Any], prev_hash: str = "0" * 64) -> Dict[str, Any]:
    """
    Signs a receipt payload, linking it to the previous hash in the ledger.
    Returns the complete verifiable receipt dictionary.
    """
    signing_key = get_or_create_signing_key()
    public_key_hex = signing_key.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")
    
    ticket_hash = compute_ticket_hash(payload, prev_hash)
    
    # Sign the ticket hash
    signed = signing_key.sign(ticket_hash.encode("utf-8"), encoder=nacl.encoding.HexEncoder)
    signature_hex = signed.signature.decode("utf-8")
    
    return {
        "payload": payload,
        "prev_hash": prev_hash,
        "ticket_hash": ticket_hash,
        "signature": signature_hex,
        "public_key": public_key_hex
    }


def verify_receipt(
    receipt_data: Dict[str, Any], 
    expected_prev_hash: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Cryptographically verifies:
    1. Canonical ticket_hash recomputation
    2. Ed25519 signature validity against public key
    3. Hash-chain linkage (if expected_prev_hash provided)
    """
    try:
        payload = receipt_data.get("payload", {})
        prev_hash = receipt_data.get("prev_hash", "")
        ticket_hash = receipt_data.get("ticket_hash", "")
        signature_hex = receipt_data.get("signature", "")
        public_key_hex = receipt_data.get("public_key", "")

        # 1. Verify prev_hash link
        if expected_prev_hash and prev_hash != expected_prev_hash:
            return False, f"Broken hash chain: expected prev_hash {expected_prev_hash}, got {prev_hash}"

        # 2. Verify ticket_hash computation
        computed_hash = compute_ticket_hash(payload, prev_hash)
        if computed_hash != ticket_hash:
            return False, f"Hash mismatch: computed {computed_hash}, got {ticket_hash}"

        # 3. Verify Ed25519 signature
        verify_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
        verify_key.verify(ticket_hash.encode("utf-8"), bytes.fromhex(signature_hex))
        
        return True, "Valid signature and tamper-evident hash chain."
    except Exception as e:
        return False, f"Verification failed: {str(e)}"
