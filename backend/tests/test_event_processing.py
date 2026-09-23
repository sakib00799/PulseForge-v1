from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.events.schemas import EventCreate
from app.modules.events.service import create_event_fingerprint


def test_event_fingerprint_is_stable_and_service_scoped() -> None:
    service_id = uuid4()

    assert create_event_fingerprint(service_id, "database_timeout") == create_event_fingerprint(
        service_id, " DATABASE_TIMEOUT "
    )
    assert create_event_fingerprint(service_id, "DATABASE_TIMEOUT") != create_event_fingerprint(
        uuid4(), "DATABASE_TIMEOUT"
    )


def test_event_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        EventCreate(
            event_id="evt-1",
            event_type="DATABASE_TIMEOUT",
            level="ERROR",
            message="Timed out",
            occurred_at=datetime.now(),
        )


def test_valid_event_payload() -> None:
    payload = EventCreate(
        event_id="evt-1",
        event_type="DATABASE_TIMEOUT",
        level="ERROR",
        message="Timed out",
        occurred_at=datetime.now(timezone.utc),
        metadata={"timeout_ms": 5000},
    )

    assert payload.metadata["timeout_ms"] == 5000
