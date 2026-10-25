"""Read-only liveness snapshot and its FastAPI route.

This module is intentionally dependency-free: it never imports
``backend.server``, ``backend.core.state_store``, Redis, the network layer, or
the configuration. A probe (or its tests) can therefore exercise the endpoint
without starting background workers or performing any application I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

SERVICE_NAME = "robotrader"
HEALTH_PATH = "/api/v1/health"


def health_snapshot(now: datetime | None = None) -> Dict[str, Any]:
    """Build the three-field liveness snapshot.

    ``now`` is injectable so tests can pin the clock; production callers use the
    current UTC instant. The emitted timestamp is ISO-8601 UTC with a trailing
    ``Z`` and an optional fractional part.
    """
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    timestamp = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"status": "ok", "service": SERVICE_NAME, "timestamp": timestamp}


health_router = APIRouter()


@health_router.get(HEALTH_PATH)
def get_health() -> Dict[str, Any]:
    """Return the process liveness snapshot; always HTTP 200, read-only."""
    return health_snapshot()
