"""
Satellite-local schema for P6 (Cryptographic Consent Signal Propagation).

Structural privacy guarantee (see PATENT.md Component 1 / ASSUMPTIONS.md):
ConsentToken has NO raw_identifier column, NOT EVEN AN OPTIONAL ONE. The
raw data subject identifier is a function parameter to
ConsentTokenEmitter.emit() and is never assigned to any ORM-mapped
attribute anywhere in this module. See tests/boundary/
test_no_raw_identifier_ever_stored.py, which asserts this structurally
by inspecting every table's column set, not by reading one code path.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OrgSigningKey(Base):
    __tablename__ = "org_signing_keys"

    org_id: Mapped[str] = mapped_column(String, primary_key=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_private_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Per-org salt used ONLY for hashing data subject identifiers.
    # Prevents cross-org rainbow-table correlation of the same subject.
    subject_hash_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RegisteredProcessor(Base):
    __tablename__ = "registered_processors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("org_signing_keys.org_id"))
    processing_activity_id: Mapped[str] = mapped_column(String, index=True)
    processor_name: Mapped[str] = mapped_column(String)
    webhook_url: Mapped[str] = mapped_column(String)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConsentToken(Base):
    """
    Contains only the SHA-256 hash of the data subject identifier —
    see module docstring. Do not add a raw_identifier column here.
    """

    __tablename__ = "consent_tokens"

    token_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("org_signing_keys.org_id"))
    hashed_subject: Mapped[str] = mapped_column(String, index=True, nullable=False)
    processing_activity_id: Mapped[str] = mapped_column(String, index=True)
    decision: Mapped[str] = mapped_column(String)  # "grant" | "withdraw"
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    canonical_payload: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class PropagationAttempt(Base):
    __tablename__ = "propagation_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    token_id: Mapped[str] = mapped_column(String, ForeignKey("consent_tokens.token_id"))
    processor_id: Mapped[str] = mapped_column(String, ForeignKey("registered_processors.id"))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String)  # "success" | "failure" | "pending"
    response_summary: Mapped[str] = mapped_column(Text, default="")


class AcknowledgementReceipt(Base):
    __tablename__ = "acknowledgement_receipts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    attempt_id: Mapped[str] = mapped_column(String, ForeignKey("propagation_attempts.id"))
    token_id: Mapped[str] = mapped_column(String, ForeignKey("consent_tokens.token_id"))
    processor_id: Mapped[str] = mapped_column(String, ForeignKey("registered_processors.id"))
    canonical_payload: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PropagationRecord(Base):
    """
    Append-only hash chain. record_hash = sha256(previous_hash + content).
    Chain is scoped per processing_activity_id via sequence_number, so
    verify_full_chain() can walk one activity's history independently.
    """

    __tablename__ = "propagation_records"
    __table_args__ = (
        UniqueConstraint("processing_activity_id", "sequence_number", name="uq_chain_seq"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    processing_activity_id: Mapped[str] = mapped_column(String, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    record_type: Mapped[str] = mapped_column(String)  # dispatch|ack|escalation|vendor_flag
    record_content: Mapped[str] = mapped_column(Text, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)
    record_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EscalationRecord(Base):
    __tablename__ = "escalation_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    token_id: Mapped[str] = mapped_column(String, ForeignKey("consent_tokens.token_id"))
    processor_id: Mapped[str] = mapped_column(String, ForeignKey("registered_processors.id"))
    stage: Mapped[str] = mapped_column(String)  # "retry" | "human" | "vendor_flag"
    retry_attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class VendorFlagRecord(Base):
    __tablename__ = "vendor_flag_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("org_signing_keys.org_id"))
    processor_id: Mapped[str] = mapped_column(String, ForeignKey("registered_processors.id"))
    token_id: Mapped[str] = mapped_column(String, ForeignKey("consent_tokens.token_id"))
    reason: Mapped[str] = mapped_column(Text)
    pushed_to_core: Mapped[bool] = mapped_column(Boolean, default=False)
    core_finding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
