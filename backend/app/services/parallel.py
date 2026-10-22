"""Run independent repository calls concurrently.

Each Supabase call is an HTTP round trip (~100 ms from Algeria), so a screen
that needs nine reads waits ~1 s when they run one after another. Endpoints
are sync (FastAPI runs them in its thread pool); this fans their independent
reads out on a shared pool so they cost about one round trip.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_pool = ThreadPoolExecutor(max_workers=32, thread_name_prefix="repo")


def gather(**calls: Callable[[], Any]) -> dict[str, Any]:
    """gather(a=lambda: ..., b=lambda: ...) -> {"a": ..., "b": ...}; re-raises the first error."""
    futures = {name: _pool.submit(fn) for name, fn in calls.items()}
    return {name: future.result() for name, future in futures.items()}
