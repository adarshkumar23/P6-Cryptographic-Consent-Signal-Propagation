"""
Dual-path migration: extends core's existing consent_records table
with a propagation_status column IF AND ONLY IF an equivalent column
does not already exist. Per ASSUMPTIONS.md, the real consent_records
schema was not available to verify in this build environment — this
migration is written to be safe to run against an unknown-but-real
schema rather than assuming column absence.

This is a template for Alembic; adapt `revision`/`down_revision` to
core's actual migration chain when applying.
"""
from alembic import op
import sqlalchemy as sa

revision = "p6_0001_consent_propagation_records"
down_revision = None  # set to core's current head when applying

EXISTING_STATUS_COLUMN_CANDIDATES = (
    "propagation_status",
    "consent_propagation_status",
    "downstream_propagation_status",
)


def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        raise RuntimeError(
            f"expected core table {table_name!r} to already exist — this "
            "satellite extends an existing production table, it does not "
            "create it. Verify core's real schema before applying."
        )
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    existing = _existing_columns("consent_records")

    already_present = existing & set(EXISTING_STATUS_COLUMN_CANDIDATES)
    if already_present:
        # consent_records already tracks propagation status under a
        # different name — extend that column's semantics in
        # application code rather than adding a duplicate one.
        return

    op.add_column(
        "consent_records",
        sa.Column("propagation_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "consent_records",
        sa.Column("propagation_last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    existing = _existing_columns("consent_records")
    if "propagation_status" in existing:
        op.drop_column("consent_records", "propagation_status")
    if "propagation_last_verified_at" in existing:
        op.drop_column("consent_records", "propagation_last_verified_at")
