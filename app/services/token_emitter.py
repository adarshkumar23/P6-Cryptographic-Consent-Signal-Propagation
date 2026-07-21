"""
PATENT.md Component 1 — Signed Consent Token Emission.

The raw data_subject_id is a function parameter ONLY. It is hashed
immediately and the hash — never the raw value — is the only thing
that touches an ORM-mapped attribute. See ConsentToken in app.models
(no raw_identifier column exists) and
tests/boundary/test_no_raw_identifier_ever_stored.py.
"""
import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crypto.keys import load_private_key
from app.crypto.signing import canonicalize, sign_payload
from app.models import ConsentToken, OrgSigningKey

VALID_DECISIONS = {"grant", "withdraw"}


def _hash_subject(data_subject_id: str, salt: bytes) -> str:
    return hashlib.sha256(salt + data_subject_id.encode("utf-8")).hexdigest()


class ConsentTokenEmitter:
    def __init__(self, session: Session):
        self.session = session

    def emit(
        self,
        *,
        data_subject_id: str,
        processing_activity_id: str,
        decision: str,
        org_id: str,
    ) -> ConsentToken:
        if decision not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of {VALID_DECISIONS}, got {decision!r}")

        org_key = self.session.get(OrgSigningKey, org_id)
        if org_key is None:
            raise ValueError(f"no signing key registered for org {org_id!r}")

        hashed_subject = _hash_subject(data_subject_id, org_key.subject_hash_salt)
        # data_subject_id goes out of scope here; nothing below references it.

        token_id = str(uuid.uuid4())
        issued_at = datetime.now(timezone.utc)
        payload = {
            "token_id": token_id,
            "hashed_subject": hashed_subject,
            "processing_activity_id": processing_activity_id,
            "decision": decision,
            "issued_at": issued_at.isoformat(),
        }

        private_key = load_private_key(org_key.encrypted_private_key)
        signature = sign_payload(private_key, payload)

        token = ConsentToken(
            token_id=token_id,
            org_id=org_id,
            hashed_subject=hashed_subject,
            processing_activity_id=processing_activity_id,
            decision=decision,
            issued_at=issued_at,
            canonical_payload=canonicalize(payload).decode("utf-8"),
            signature=signature,
        )
        self.session.add(token)
        self.session.flush()
        return token
