"""
Per-organization Ed25519 keypair generation and encrypted-at-rest
storage. The encryption key (SATELLITE_KEK) is satellite-local and
architecturally separate from any core production secret — see
ASSUMPTIONS.md. Core never sees a private key; it only ever receives
already-signed, already-verified records (see scripts/boundary_audit.sh).
"""
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import get_settings


class KeypairMaterial:
    def __init__(
        self,
        org_id: str,
        public_key: Ed25519PublicKey,
        private_key: Ed25519PrivateKey,
        public_key_bytes: bytes,
        encrypted_private_key: bytes,
        subject_hash_salt: bytes,
    ):
        self.org_id = org_id
        self.public_key = public_key
        self.private_key = private_key
        self.public_key_bytes = public_key_bytes
        self.encrypted_private_key = encrypted_private_key
        self.subject_hash_salt = subject_hash_salt


def _fernet() -> Fernet:
    kek = get_settings().satellite_kek
    if not kek:
        raise RuntimeError(
            "SATELLITE_KEK is not set. This key is satellite-local and must "
            "never be core's Fernet key — see ASSUMPTIONS.md."
        )
    return Fernet(kek.encode() if isinstance(kek, str) else kek)


def generate_org_keypair(org_id: str) -> KeypairMaterial:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    encrypted_private_key = _fernet().encrypt(private_bytes)
    subject_hash_salt = os.urandom(16)

    return KeypairMaterial(
        org_id=org_id,
        public_key=public_key,
        private_key=private_key,
        public_key_bytes=public_bytes,
        encrypted_private_key=encrypted_private_key,
        subject_hash_salt=subject_hash_salt,
    )


def load_private_key(encrypted_private_key: bytes) -> Ed25519PrivateKey:
    raw = _fernet().decrypt(encrypted_private_key)
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key(public_key_bytes: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(public_key_bytes)


def generate_processor_keypair() -> tuple[Ed25519PrivateKey, bytes]:
    """Convenience for tests/registration flows that mint a processor's
    own keypair. In production the processor generates and registers
    its own keypair; the satellite never holds a processor's private
    key."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, public_bytes
