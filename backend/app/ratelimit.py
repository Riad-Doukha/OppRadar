"""Per-IP rate limits for endpoints anyone can hit (no account needed, or the
shared demo account). In-memory, so it holds for the single API instance we
run; the client IP comes from uvicorn's --proxy-headers behind the host's proxy.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def limit(name: str, per_minute: int):
    """Dependency: 429 once this IP made `per_minute` calls to `name` in 60 s."""

    def check(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with _lock:
            hits = _hits[(name, ip)]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= per_minute:
                retry = int(60 - (now - hits[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many requests. Please wait a moment and try again.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    return check


def reset() -> None:
    """Forget every counter (tests)."""
    with _lock:
        _hits.clear()
