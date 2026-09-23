"""Create organization services.

Revision ID: 0003_services
Revises: 0002_refresh_tokens
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_services"
down_revision = "0002_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    environment = postgresql.ENUM(
        "PRODUCTION",
        "STAGING",
        "DEVELOPMENT",
        name="service_environment",
        create_type=False,
    )
    service_status = postgresql.ENUM(
        "OPERATIONAL",
        "DEGRADED",
        "MAINTENANCE",
        "DISABLED",
        name="service_status",
        create_type=False,
    )
    environment.create(op.get_bind(), checkfirst=True)
    service_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", environment, nullable=False),
        sa.Column("status", service_status, server_default="OPERATIONAL", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "slug", name="uq_service_organization_slug"
        ),
    )
    op.create_index("ix_services_organization_id", "services", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_services_organization_id", table_name="services")
    op.drop_table("services")
    postgresql.ENUM(name="service_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="service_environment").drop(op.get_bind(), checkfirst=True)
