"""initial satellite schema

Revision ID: 0001_initial_satellite_schema
Revises:
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_satellite_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "org_signing_keys",
        sa.Column("org_id", sa.String(), primary_key=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_private_key", sa.LargeBinary(), nullable=False),
        sa.Column("subject_hash_salt", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "registered_processors",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("org_signing_keys.org_id"), nullable=False),
        sa.Column("processing_activity_id", sa.String(), nullable=False, index=True),
        sa.Column("processor_name", sa.String(), nullable=False),
        sa.Column("webhook_url", sa.String(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "consent_tokens",
        sa.Column("token_id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("org_signing_keys.org_id"), nullable=False),
        sa.Column("hashed_subject", sa.String(), nullable=False, index=True),
        sa.Column("processing_activity_id", sa.String(), nullable=False, index=True),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_payload", sa.Text(), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
    )

    op.create_table(
        "propagation_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("token_id", sa.String(), sa.ForeignKey("consent_tokens.token_id"), nullable=False),
        sa.Column(
            "processor_id", sa.String(), sa.ForeignKey("registered_processors.id"), nullable=False
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("response_summary", sa.Text(), nullable=False, server_default=""),
    )

    op.create_table(
        "acknowledgement_receipts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "attempt_id", sa.String(), sa.ForeignKey("propagation_attempts.id"), nullable=False
        ),
        sa.Column("token_id", sa.String(), sa.ForeignKey("consent_tokens.token_id"), nullable=False),
        sa.Column(
            "processor_id", sa.String(), sa.ForeignKey("registered_processors.id"), nullable=False
        ),
        sa.Column("canonical_payload", sa.Text(), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "propagation_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("processing_activity_id", sa.String(), nullable=False, index=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(), nullable=False),
        sa.Column("record_content", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.String(), nullable=False),
        sa.Column("record_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("processing_activity_id", "sequence_number", name="uq_chain_seq"),
    )

    op.create_table(
        "escalation_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("token_id", sa.String(), sa.ForeignKey("consent_tokens.token_id"), nullable=False),
        sa.Column(
            "processor_id", sa.String(), sa.ForeignKey("registered_processors.id"), nullable=False
        ),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("retry_attempt_number", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "vendor_flag_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("org_signing_keys.org_id"), nullable=False),
        sa.Column(
            "processor_id", sa.String(), sa.ForeignKey("registered_processors.id"), nullable=False
        ),
        sa.Column("token_id", sa.String(), sa.ForeignKey("consent_tokens.token_id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("pushed_to_core", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("core_finding_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("vendor_flag_records")
    op.drop_table("escalation_records")
    op.drop_table("propagation_records")
    op.drop_table("acknowledgement_receipts")
    op.drop_table("propagation_attempts")
    op.drop_table("consent_tokens")
    op.drop_table("registered_processors")
    op.drop_table("org_signing_keys")
