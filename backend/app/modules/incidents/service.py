from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.events.models import Event, EventLevel
from app.modules.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
)

INCIDENT_THRESHOLD = 5
INCIDENT_WINDOW_SECONDS = 60


def find_active_incident(session: Session, event: Event) -> Incident | None:
    return session.scalar(
        select(Incident).where(
            Incident.service_id == event.service_id,
            Incident.fingerprint == event.fingerprint,
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED]),
        )
    )


def link_event_if_needed(session: Session, incident: Incident, event: Event) -> None:
    already_linked = session.scalar(
        select(IncidentEvent.id).where(
            IncidentEvent.incident_id == incident.id,
            IncidentEvent.event_id == event.id,
        )
    )
    if already_linked is None:
        session.add(IncidentEvent(incident_id=incident.id, event_id=event.id))


def evaluate_event_for_incident(session: Session, event: Event) -> Incident | None:
    if event.level not in {EventLevel.ERROR, EventLevel.CRITICAL}:
        return None

    active_incident = find_active_incident(session, event)
    if active_incident is not None:
        link_event_if_needed(session, active_incident, event)
        if event.level == EventLevel.CRITICAL:
            active_incident.severity = IncidentSeverity.SEV_1
        return active_incident

    window_start = event.occurred_at - timedelta(seconds=INCIDENT_WINDOW_SECONDS)
    matching_count = session.scalar(
        select(func.count(Event.id)).where(
            Event.service_id == event.service_id,
            Event.fingerprint == event.fingerprint,
            Event.level.in_([EventLevel.ERROR, EventLevel.CRITICAL]),
            Event.occurred_at >= window_start,
            Event.occurred_at <= event.occurred_at,
        )
    )
    if (matching_count or 0) < INCIDENT_THRESHOLD:
        return None

    severity = (
        IncidentSeverity.SEV_1
        if event.level == EventLevel.CRITICAL
        else IncidentSeverity.SEV_2
    )
    try:
        with session.begin_nested():
            incident = Incident(
                organization_id=event.organization_id,
                service_id=event.service_id,
                title=f"Repeated {event.event_type} events",
                description=(
                    f"Detected at least {INCIDENT_THRESHOLD} matching error events "
                    f"within {INCIDENT_WINDOW_SECONDS} seconds."
                ),
                severity=severity,
                status=IncidentStatus.OPEN,
                detected_at=event.occurred_at,
                fingerprint=event.fingerprint,
            )
            session.add(incident)
            session.flush()
    except IntegrityError:
        # Another request created the same active incident. The savepoint keeps
        # the current event transaction alive while the database picks one winner.
        active_incident = find_active_incident(session, event)
        if active_incident is None:
            raise
        link_event_if_needed(session, active_incident, event)
        if event.level == EventLevel.CRITICAL:
            active_incident.severity = IncidentSeverity.SEV_1
        return active_incident

    matching_event_ids = session.scalars(
        select(Event.id).where(
            Event.service_id == event.service_id,
            Event.fingerprint == event.fingerprint,
            Event.level.in_([EventLevel.ERROR, EventLevel.CRITICAL]),
            Event.occurred_at >= window_start,
            Event.occurred_at <= event.occurred_at,
        )
    ).all()
    session.add_all(
        IncidentEvent(incident_id=incident.id, event_id=event_id)
        for event_id in matching_event_ids
    )
    return incident
