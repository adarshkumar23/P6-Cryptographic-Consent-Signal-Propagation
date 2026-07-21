"""
Adds a registered_processors table to core IF core does not already
have an equivalent processor/vendor registry table this could extend
instead. Per ASSUMPTIONS.md this check is a runtime guard against an
unverified real schema, not a confirmed absence.
"""
from alembic import op
import sqlalchemy as sa

revision = "p6_0002_registered_processors"
down_revision = "p6_0001_consent_propagation_records"

CANDIDATE_EXISTING_TABLES = ("registered_processors", "consent_processors", "data_processors")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if existing_tables & set(CANDIDATE_EXISTING_TABLES):
        # Core already has a processor registry table under one of
        # these names — extend it in application code instead of
        # creating a duplicate.
        return

    op.create_table(
        "registered_processors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("processing_activity_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("processor_name", sa.String(length=255), nullable=False),
        sa.Column("webhook_url", sa.String(length=1024), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "registered_processors" in inspector.get_table_names():
        op.drop_table("registered_processors")
