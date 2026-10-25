"""Per-IP rate limits for endpoints anyone can hit (no account needed, or the
shared demo account). In-memory, so it holds for the single API instance we
run. Behind the host's proxy, set CLIENT_IP_HEADER (see config.py).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    header = get_settings().client_ip_header.lower()
    value = request.headers.get(header, "") if header else ""
    if header == "x-forwarded-for":
        value = value.rsplit(",", 1)[-1]  # leftmost entries are client-supplied
    if value.strip():
        return value.strip()
    return request.client.host if request.client else "unknown"


def limit(name: str, per_minute: int):
    """Dependency: 429 once this IP made `per_minute` calls to `name` in 60 s."""

    def check(request: Request) -> None:
        ip = client_ip(request)
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
