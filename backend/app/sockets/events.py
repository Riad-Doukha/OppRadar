"""WebSocket events (Socket.IO).

Clients connect with `auth: {token: <supabase access token>}` and are placed in
a private `user:<id>` room — nobody can subscribe to someone else's events.

Events the frontend listens to:
  - `document:progress` — {id, status, error?} while an upload is read/extracted
  - `ingest:progress`   — how far the ingestion pipeline has got (ingestion phase)
  - `match:update`      — new matches for the current user (matching phase)
"""

from __future__ import annotations

import logging
from typing import Any

import socketio

from app.auth import AuthError, decode_token
from app.config import get_settings

logger = logging.getLogger(__name__)

# Async server; mounted at /ws in app.main.
sio_app = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=get_settings().cors_origin_list,
)


def user_room(user_id: str) -> str:
    return f"user:{user_id}"


@sio_app.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    token = (auth or {}).get("token")
    if not token:
        raise socketio.exceptions.ConnectionRefusedError("missing token")
    try:
        user_id = decode_token(token)["sub"]
    except (AuthError, KeyError) as exc:
        raise socketio.exceptions.ConnectionRefusedError("invalid token") from exc
    await sio_app.save_session(sid, {"user_id": user_id})
    await sio_app.enter_room(sid, user_room(user_id))
    logger.debug("ws connected: %s (user %s)", sid, user_id)


@sio_app.event
async def disconnect(sid: str) -> None:
    logger.debug("ws disconnected: %s", sid)


async def emit_to_user(user_id: str, event: str, payload: dict[str, Any]) -> None:
    await sio_app.emit(event, payload, room=user_room(user_id))


async def broadcast_ingest_progress(payload: dict) -> None:
    await sio_app.emit("ingest:progress", payload)


async def broadcast_match_update(user_id: str, payload: dict) -> None:
    await emit_to_user(user_id, "match:update", payload)
