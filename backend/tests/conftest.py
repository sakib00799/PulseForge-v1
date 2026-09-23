import pytest

from app.core.rate_limit import rate_limiter


@pytest.fixture(autouse=True)
def reset_process_rate_limiter() -> None:
    rate_limiter.reset()
    yield
    rate_limiter.reset()
