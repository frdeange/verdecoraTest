"""In-memory sliding-window rate limiter for Upload Web (#119).

Limits are per user (``oid`` from the authenticated session) and per
action type.  When a limit is exceeded the middleware returns
``429 Too Many Requests`` with a ``Retry-After`` header.

No external store (Redis) is required — this is suitable for single-
instance PoC deployments.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse


@dataclass
class _RateLimit:
    max_requests: int
    window_seconds: int


# Action → limit definition
RATE_LIMITS: dict[str, _RateLimit] = {
    "sas_generation": _RateLimit(max_requests=30, window_seconds=60),
    "file_upload": _RateLimit(max_requests=100, window_seconds=3600),
    "session_creation": _RateLimit(max_requests=10, window_seconds=3600),
}

# Path pattern → action mapping
_PATH_ACTION_MAP: list[tuple[str, str, str]] = [
    # (method, path_suffix, action)
    ("POST", "/sas", "sas_generation"),
    ("POST", "/files", "file_upload"),
    ("POST", "/sessions", "session_creation"),
]


@dataclass
class _SlidingWindow:
    timestamps: list[float] = field(default_factory=list)

    def prune(self, window_seconds: int, now: float) -> None:
        cutoff = now - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]

    def count(self) -> int:
        return len(self.timestamps)

    def add(self, now: float) -> None:
        self.timestamps.append(now)


class RateLimiterStore:
    """Thread-safe in-memory sliding-window store keyed by ``(oid, action)``."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, str], _SlidingWindow] = defaultdict(_SlidingWindow)

    def check_and_record(self, oid: str, action: str) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)``."""
        limit = RATE_LIMITS.get(action)
        if limit is None:
            return True, 0

        key = (oid, action)
        window = self._windows[key]
        now = time.monotonic()
        window.prune(limit.window_seconds, now)

        if window.count() >= limit.max_requests:
            retry_after = int(limit.window_seconds - (now - window.timestamps[0])) + 1
            return False, max(retry_after, 1)

        window.add(now)
        return True, 0


_store = RateLimiterStore()


def _resolve_action(method: str, path: str) -> str | None:
    upper_method = method.upper()
    for m, suffix, action in _PATH_ACTION_MAP:
        if upper_method == m and path.rstrip("/").endswith(suffix):
            return action
    return None


def _get_user_oid(request: Request) -> str | None:
    user: Any = getattr(request.state, "authenticated_user", None)
    if user is not None:
        return getattr(user, "oid", None)
    return None


async def rate_limit_check(request: Request) -> Response | None:
    """Call from a middleware or dependency; returns a 429 response or ``None`` if allowed."""
    action = _resolve_action(request.method, request.url.path)
    if action is None:
        return None

    oid = _get_user_oid(request)
    if oid is None:
        return None

    allowed, retry_after = _store.check_and_record(oid, action)
    if allowed:
        return None

    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
        headers={"Retry-After": str(retry_after)},
    )
