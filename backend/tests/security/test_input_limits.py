from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.events.schemas import EventCreate


def test_oversized_event_metadata_is_rejected() -> None:
    with pytest.raises(ValidationError, match="metadata must not exceed 32768 bytes"):
        EventCreate(
            event_id="oversized-1",
            event_type="SECURITY_TEST",
            level="ERROR",
            message="Oversized metadata",
            occurred_at=datetime.now(timezone.utc),
            metadata={"payload": "x" * (33 * 1024)},
        )


def test_metadata_at_reasonable_size_is_accepted() -> None:
    event = EventCreate(
        event_id="normal-1",
        event_type="SECURITY_TEST",
        level="ERROR",
        message="Normal metadata",
        occurred_at=datetime.now(timezone.utc),
        metadata={"payload": "x" * 1024},
    )
    assert len(event.metadata["payload"]) == 1024
