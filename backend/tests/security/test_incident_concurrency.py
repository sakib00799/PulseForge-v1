from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.modules.events.models import Event, EventLevel
from app.modules.events.service import create_event_fingerprint
from app.modules.incidents.models import Incident, IncidentEvent, IncidentStatus
from app.modules.incidents.service import evaluate_event_for_incident
from app.modules.organizations.models import Organization
from app.modules.services.models import Service, ServiceEnvironment
from app.modules.users.models import User


def test_parallel_matching_events_create_exactly_one_active_incident(tmp_path: object) -> None:
    database_path = tmp_path / "incident-concurrency.sqlite3"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    occurred_at = datetime.now(timezone.utc)

    with session_factory() as session:
        user = User(
            email="incident-concurrency@example.com",
            password_hash="unused",
            full_name="Concurrency Test",
        )
        session.add(user)
        session.flush()
        organization = Organization(
            name="Concurrency Org",
            slug="concurrency-org",
            created_by_id=user.id,
        )
        session.add(organization)
        session.flush()
        service = Service(
            organization_id=organization.id,
            name="Payments",
            slug="payments",
            environment=ServiceEnvironment.DEVELOPMENT,
        )
        session.add(service)
        session.flush()
        fingerprint = create_event_fingerprint(service.id, "DATABASE_TIMEOUT")
        for index in range(3):
            session.add(
                Event(
                    organization_id=organization.id,
                    service_id=service.id,
                    event_id=f"preloaded-{index}",
                    event_type="DATABASE_TIMEOUT",
                    level=EventLevel.ERROR,
                    message="Database timed out",
                    occurred_at=occurred_at,
                    fingerprint=fingerprint,
                    metadata_json={},
                )
            )
        session.commit()
        organization_id = organization.id
        service_id = service.id

    barrier = Barrier(2)

    def ingest(event_number: int) -> None:
        barrier.wait(timeout=10)
        with session_factory() as session:
            event = Event(
                organization_id=organization_id,
                service_id=service_id,
                event_id=f"parallel-{event_number}",
                event_type="DATABASE_TIMEOUT",
                level=EventLevel.ERROR,
                message="Database timed out",
                occurred_at=occurred_at,
                fingerprint=fingerprint,
                metadata_json={},
            )
            session.add(event)
            session.flush()
            evaluate_event_for_incident(session, event)
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(ingest, number) for number in (4, 5)]
        for future in futures:
            future.result(timeout=30)

    with session_factory() as session:
        event_count = session.scalar(select(func.count(Event.id)))
        active_incidents = session.scalars(
            select(Incident).where(
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED])
            )
        ).all()
        link_count = session.scalar(select(func.count(IncidentEvent.id)))

    engine.dispose()
    assert event_count == 5
    assert len(active_incidents) == 1
    assert link_count == 5
