"""
Ed25519 payload signing/verification. This module has no dependency on
app.models or app.db — it operates purely on dicts and key objects so
it can be tested in complete isolation before anything else is built
on top of it (PATENT.md Component 1 & 2).
"""
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonicalize(payload: dict) -> bytes:
    """Deterministic JSON encoding so signature verification is stable
    regardless of dict insertion order."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(private_key: Ed25519PrivateKey, payload: dict) -> bytes:
    return private_key.sign(canonicalize(payload))


def verify_signature(public_key: Ed25519PublicKey, payload: dict, signature: bytes) -> bool:
    try:
        public_key.verify(signature, canonicalize(payload))
        return True
    except InvalidSignature:
        return False
