"""On-demand rate-limit gate for user-triggered runs/ingests.

In-process, single-instance (inline execution this milestone). A durable multi-instance
limiter needs Redis — deferred with hosting; see `.lane-report.md`.
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable, Coroutine, Hashable
from typing import Any
from uuid import UUID

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from specula_api.config import settings
from specula_api.deps import get_current_user_id

# Rolling window the per-hour cap is measured over.
_WINDOW_S = 3600.0


class RateLimited(Exception):
    """A user's trigger breached the cooldown or the per-hour cap.

    Rendered as a 429 whose body matches the frozen `RateLimitError` TS shape by
    `RateLimitedRoute` (below), so it must carry the seconds a client should wait.
    """

    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"rate limited, retry after {retry_after_s}s")
        self.retry_after_s = retry_after_s


def _ceil_positive(seconds: float) -> int:
    """Whole seconds to wait, never below 1 — a 0 would tell a client to retry instantly."""
    return max(1, math.ceil(seconds))


class _InProcessLimiter:
    """Per-user cooldown + sliding-window cap. Process-local (see module docstring)."""

    def __init__(self) -> None:
        self._hits: dict[Hashable, deque[float]] = defaultdict(deque)

    def check(self, key: Hashable, *, per_hour: int, cooldown_s: float, now: float) -> None:
        """Record a trigger under `key` (a per-user, per-kind bucket), or raise `RateLimited`
        if it breaches a limit."""
        hits = self._hits[key]
        while hits and now - hits[0] >= _WINDOW_S:
            hits.popleft()

        if hits:
            since_last = now - hits[-1]
            if since_last < cooldown_s:
                raise RateLimited(_ceil_positive(cooldown_s - since_last))

        if len(hits) >= per_hour:
            oldest = hits[0] if hits else now
            raise RateLimited(_ceil_positive(_WINDOW_S - (now - oldest)))

        hits.append(now)

    def clear(self) -> None:
        self._hits.clear()


# Process-global limiter + clock. The clock is a seam so tests can advance time past the
# cooldown without waiting; production uses a monotonic wall clock.
_limiter = _InProcessLimiter()
_clock: Callable[[], float] = time.monotonic


def enforce_rate_limit(user_id: UUID) -> None:
    """Gate a discovery RUN for `user_id`, or raise `RateLimited` on breach — a 60s cooldown
    plus an hourly cap, since a run fires many expensive web searches and rapid re-triggers are
    almost always accidental."""
    _limiter.check(
        ("run", user_id),
        per_hour=settings.run_rate_limit_per_hour,
        cooldown_s=settings.run_cooldown_s,
        now=_clock(),
    )


def enforce_ingest_rate_limit(user_id: UUID) -> None:
    """Gate an approve->ingest for `user_id`, or raise `RateLimited` on breach. Its OWN bucket,
    with NO cooldown: approving companies one after another in the queue is intended, so only an
    hourly cap bounds the crawl+LLM cost — the run cooldown must never throttle it."""
    _limiter.check(
        ("ingest", user_id),
        per_hour=settings.ingest_rate_limit_per_hour,
        cooldown_s=0,
        now=_clock(),
    )


async def rate_limit_guard(user_id: UUID = Depends(get_current_user_id)) -> None:
    """FastAPI dependency form of the run gate — apply to on-demand run-trigger endpoints."""
    enforce_rate_limit(user_id)


class RateLimitedRoute(APIRoute):
    """Renders a `RateLimited` raised anywhere in a route (dependency or handler body) as a 429
    whose body is the bare frozen `RateLimitError` shape.

    FastAPI's default `HTTPException` handler wraps bodies in `{"detail": ...}`, and the only
    app-level exception handler seam lives in `main.py` (owned exclusively by the OBS lane). A
    per-router `route_class` keeps the rendering inside this lane's files instead.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RateLimited as exc:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "retryAfterS": exc.retry_after_s},
                    headers={"Retry-After": str(exc.retry_after_s)},
                )

        return handler
