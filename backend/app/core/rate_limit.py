"""Process-local request rate limiting.

This implementation deliberately keeps PulseForge V1 dependency-free. Buckets are
not shared between backend processes and are cleared on restart. Before running
multiple API instances, replace this store with an atomic shared backend such as
Redis while keeping the same policy keys and error contract.
"""

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable

from app.core.exceptions import RateLimitError


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    limit: int
    window_seconds: int


LOGIN_RATE_LIMIT = RateLimitPolicy(limit=5, window_seconds=60)
REGISTER_RATE_LIMIT = RateLimitPolicy(limit=3, window_seconds=60 * 60)
REFRESH_RATE_LIMIT = RateLimitPolicy(limit=20, window_seconds=60)
EVENT_INGESTION_RATE_LIMIT = RateLimitPolicy(limit=100, window_seconds=60)
MAX_RATE_LIMIT_WINDOW_SECONDS = max(
    LOGIN_RATE_LIMIT.window_seconds,
    REGISTER_RATE_LIMIT.window_seconds,
    REFRESH_RATE_LIMIT.window_seconds,
    EVENT_INGESTION_RATE_LIMIT.window_seconds,
)


class InMemoryRateLimiter:
    """Thread-safe sliding-window limiter for a single application process."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._checks = 0

    def check(self, key: str, policy: RateLimitPolicy) -> None:
        now = self._clock()
        cutoff = now - policy.window_seconds
        with self._lock:
            self._checks += 1
            if self._checks % 1_000 == 0:
                self._remove_idle_buckets(now - MAX_RATE_LIMIT_WINDOW_SECONDS)

            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= policy.limit:
                retry_after = max(1, ceil(bucket[0] + policy.window_seconds - now))
                raise RateLimitError(retry_after)
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._checks = 0

    def _remove_idle_buckets(self, cutoff: float) -> None:
        idle = [key for key, bucket in self._buckets.items() if not bucket or bucket[-1] <= cutoff]
        for key in idle:
            self._buckets.pop(key, None)


def private_rate_limit_key(scope: str, *identity_parts: object) -> str:
    identity = "\x1f".join(str(part).strip().lower() for part in identity_parts)
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"{scope}:{digest}"


def client_ip(request: object) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return str(host) if host else "unknown"


rate_limiter = InMemoryRateLimiter()
