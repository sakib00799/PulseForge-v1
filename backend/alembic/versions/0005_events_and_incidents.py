"""Create telemetry events and minimal incidents.

Revision ID: 0005_events_incidents
Revises: 0004_api_keys
Create Date: 2026-09-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_events_incidents"
down_revision = "0004_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    event_level = postgresql.ENUM(
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", name="event_level", create_type=False
    )
    incident_severity = postgresql.ENUM(
        "SEV_1", "SEV_2", "SEV_3", "SEV_4", name="incident_severity", create_type=False
    )
    incident_status = postgresql.ENUM(
        "OPEN", "ACKNOWLEDGED", "RESOLVED", name="incident_status", create_type=False
    )
    event_level.create(op.get_bind(), checkfirst=True)
    incident_severity.create(op.get_bind(), checkfirst=True)
    incident_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("level", event_level, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "event_id", name="uq_event_service_event_id"),
    )
    op.create_index("ix_events_organization_id", "events", ["organization_id"])
    op.create_index("ix_events_service_id", "events", ["service_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_level", "events", ["level"])
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])
    op.create_index("ix_events_fingerprint", "events", ["fingerprint"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", incident_severity, nullable=False),
        sa.Column("status", incident_status, server_default="OPEN", nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"])
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_fingerprint", "incidents", ["fingerprint"])

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "event_id", name="uq_incident_event"),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"])
    op.create_index("ix_incident_events_event_id", "incident_events", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_incident_events_event_id", table_name="incident_events")
    op.drop_index("ix_incident_events_incident_id", table_name="incident_events")
    op.drop_table("incident_events")
    op.drop_index("ix_incidents_fingerprint", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_service_id", table_name="incidents")
    op.drop_index("ix_incidents_organization_id", table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_events_fingerprint", table_name="events")
    op.drop_index("ix_events_occurred_at", table_name="events")
    op.drop_index("ix_events_level", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_service_id", table_name="events")
    op.drop_index("ix_events_organization_id", table_name="events")
    op.drop_table("events")
    postgresql.ENUM(name="incident_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="incident_severity").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="event_level").drop(op.get_bind(), checkfirst=True)
