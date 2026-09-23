"""Prevent duplicate active incidents under concurrent ingestion.

Revision ID: 0008_unique_active_incident
Revises: 0007_audit_logs
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_unique_active_incident"
down_revision = "0007_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "unique_active_incident",
        "incidents",
        ["service_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'ACKNOWLEDGED')"),
    )


def downgrade() -> None:
    op.drop_index("unique_active_incident", table_name="incidents")
