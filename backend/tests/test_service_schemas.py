from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.services.models import ServiceEnvironment
from app.modules.services.schemas import ServiceCreate, ServiceUpdate


def test_service_create_accepts_valid_slug_and_environment() -> None:
    payload = ServiceCreate(
        organization_id=uuid4(),
        name="Payment Service",
        slug="payment-service",
        environment="production",
    )

    assert payload.environment == ServiceEnvironment.PRODUCTION


@pytest.mark.parametrize("slug", ["Payment Service", "payment_service", "-payment"])
def test_service_create_rejects_invalid_slug(slug: str) -> None:
    with pytest.raises(ValidationError):
        ServiceCreate(
            organization_id=uuid4(),
            name="Payment Service",
            slug=slug,
            environment="production",
        )


def test_service_update_is_partial() -> None:
    payload = ServiceUpdate(status="degraded")

    assert payload.model_dump(exclude_unset=True) == {"status": "degraded"}
