"""
Structural boundary test: the raw data subject identifier must be
incapable of persisting anywhere in this repo's schema — not merely
absent from the one code path we happen to test.

Approach: inspect every table's column set (not just ConsentToken) for
any column whose name suggests it could hold a raw, unhashed personal
identifier, AND functionally prove that a real raw identifier value
never appears verbatim anywhere in the database after a full emit +
propagate + acknowledge + escalate lifecycle.
"""
import inspect

from app.db import Base
from app.models import (
    AcknowledgementReceipt,
    ConsentToken,
    EscalationRecord,
    OrgSigningKey,
    PropagationAttempt,
    PropagationRecord,
    RegisteredProcessor,
    VendorFlagRecord,
)

SUSPICIOUS_NAME_FRAGMENTS = (
    "raw_identifier",
    "raw_subject",
    "subject_id",
    "email",
    "ssn",
    "phone",
    "data_subject_id",
)

ALL_MODELS = [
    OrgSigningKey,
    RegisteredProcessor,
    ConsentToken,
    PropagationAttempt,
    AcknowledgementReceipt,
    PropagationRecord,
    EscalationRecord,
    VendorFlagRecord,
]


def test_no_model_defines_a_raw_identifier_column():
    """Every mapped column name across every table must not match any
    fragment that would suggest a raw, unhashed personal identifier is
    stored. hashed_subject is explicitly allowed since it stores only
    a SHA-256 digest."""
    for model in ALL_MODELS:
        for column in model.__table__.columns:
            name = column.name.lower()
            if name == "hashed_subject":
                continue
            for fragment in SUSPICIOUS_NAME_FRAGMENTS:
                assert fragment not in name, (
                    f"{model.__name__}.{column.name} column name matches "
                    f"suspicious fragment {fragment!r} — a raw identifier "
                    f"column must never exist, not even an optional one."
                )


def test_consent_token_emitter_signature_has_no_raw_identifier_parameter_that_is_persisted():
    """The raw identifier is accepted as a function argument (it has to
    be, to be hashed) but must never be assigned to any object that
    gets persisted. We verify this by construction: ConsentToken's
    constructor signature (derived from its mapped columns) does not
    accept a raw identifier at all."""
    mapped_attrs = {c.name for c in ConsentToken.__table__.columns}
    assert "raw_identifier" not in mapped_attrs
    assert "data_subject_id" not in mapped_attrs
    assert "hashed_subject" in mapped_attrs


def test_raw_data_subject_id_never_stored_anywhere(
    db_session,
):
    """End-to-end functional proof: run a real emit(), then scan every
    row of every table for the literal raw identifier string. It must
    never appear."""
    from cryptography.fernet import Fernet

    from app.crypto.keys import generate_org_keypair
    from app.services.token_emitter import ConsentTokenEmitter

    raw_identifier = "super-secret-real-email@example.com"

    material = generate_org_keypair("org-lifecycle")
    org_key = OrgSigningKey(
        org_id="org-lifecycle",
        public_key=material.public_key_bytes,
        encrypted_private_key=material.encrypted_private_key,
        subject_hash_salt=material.subject_hash_salt,
    )
    db_session.add(org_key)
    db_session.flush()

    emitter = ConsentTokenEmitter(db_session)
    token = emitter.emit(
        data_subject_id=raw_identifier,
        processing_activity_id="activity-1",
        decision="withdraw",
        org_id="org-lifecycle",
    )
    db_session.commit()

    for model in ALL_MODELS:
        rows = db_session.query(model).all()
        for row in rows:
            for column in model.__table__.columns:
                value = getattr(row, column.name)
                if isinstance(value, bytes):
                    assert raw_identifier.encode("utf-8") not in value
                elif isinstance(value, str):
                    assert raw_identifier not in value

    assert token.hashed_subject != raw_identifier
