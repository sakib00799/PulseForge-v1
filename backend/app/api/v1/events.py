from datetime import datetime, timezone
from uuid import UUID

from app.core.permissions import Permission

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession, IngestionApiKey
from app.core.rate_limit import (
    EVENT_INGESTION_RATE_LIMIT,
    private_rate_limit_key,
    rate_limiter,
)
from app.modules.events.models import Event, EventLevel
from app.modules.events.schemas import EventCreate, EventIngestResponse, EventResponse
from app.modules.events.service import create_event_fingerprint
from app.modules.incidents.models import IncidentEvent
from app.modules.incidents.service import evaluate_event_for_incident
from app.modules.organizations.permissions import require_permission, get_tenant_resource_or_404

router = APIRouter(prefix="/events")


def find_incident_id(session: DbSession, event_id: UUID) -> UUID | None:
    return session.scalar(
        select(IncidentEvent.incident_id).where(IncidentEvent.event_id == event_id).limit(1)
    )


@router.post("", response_model=EventIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_event(
    payload: EventCreate,
    request: Request,
    response: Response,
    session: DbSession,
    api_key: IngestionApiKey,
) -> EventIngestResponse:
    rate_limiter.check(
        private_rate_limit_key("event-ingestion", api_key.id),
        EVENT_INGESTION_RATE_LIMIT,
    )
    existing = session.scalar(
        select(Event).where(
            Event.service_id == api_key.service_id,
            Event.event_id == payload.event_id.strip(),
        )
    )
    api_key.last_used_at = datetime.now(timezone.utc)
    if existing is not None:
        session.commit()
        response.status_code = status.HTTP_200_OK
        return EventIngestResponse(
            event=EventResponse.model_validate(existing),
            duplicate=True,
            incident_id=find_incident_id(session, existing.id),
        )

    event = Event(
        organization_id=api_key.organization_id,
        service_id=api_key.service_id,
        event_id=payload.event_id.strip(),
        event_type=payload.event_type.strip().upper(),
        level=payload.level,
        message=payload.message.strip(),
        occurred_at=payload.occurred_at,
        fingerprint=create_event_fingerprint(api_key.service_id, payload.event_type),
        metadata_json=payload.metadata,
        trace_id=payload.trace_id,
        request_id=payload.request_id,
    )
    session.add(event)
    try:
        session.flush()
    except IntegrityError:
        # The unique constraint protects concurrent duplicate deliveries.
        session.rollback()
        existing = session.scalar(
            select(Event).where(
                Event.service_id == api_key.service_id,
                Event.event_id == payload.event_id.strip(),
            )
        )
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return EventIngestResponse(
            event=EventResponse.model_validate(existing),
            duplicate=True,
            incident_id=find_incident_id(session, existing.id),
        )

    incident = evaluate_event_for_incident(session, event)
    session.commit()
    session.refresh(event)
    return EventIngestResponse(
        event=EventResponse.model_validate(event),
        duplicate=False,
        incident_id=incident.id if incident is not None else None,
    )


@router.get("", response_model=list[EventResponse])
def list_events(
    organization_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    service_id: UUID | None = None,
    level: EventLevel | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Event]:
    require_permission(Permission.EVENT_READ)(session, organization_id, current_user.id)
    query = select(Event).where(Event.organization_id == organization_id)
    if service_id is not None:
        query = query.where(Event.service_id == service_id)
    if level is not None:
        query = query.where(Event.level == level)
    return list(
        session.scalars(
            query.order_by(Event.occurred_at.desc()).limit(limit).offset(offset)
        ).all()
    )


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: UUID, session: DbSession, current_user: CurrentUser) -> Event:
    event = get_tenant_resource_or_404(session, Event, event_id, current_user.id)
    require_permission(Permission.EVENT_READ)(session, event.organization_id, current_user.id)
    return event
