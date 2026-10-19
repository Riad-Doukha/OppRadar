"""WebSocket events (Socket.IO).

The frontend subscribes to:
  - `ingest:progress`  — how far the ingestion pipeline has got
  - `match:update`     — new MatchResult rows for the current profile
"""

import socketio

# Async server; mounted at /ws in app.main.
sio_app = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio_app.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    print(f"[ws] client connected: {sid}")


@sio_app.event
async def disconnect(sid: str) -> None:
    print(f"[ws] client disconnected: {sid}")


@sio_app.event
async def subscribe_profile(sid: str, profile_id: str) -> None:
    """Join a room so this client only gets its own profile's match updates."""
    await sio_app.enter_room(sid, f"profile:{profile_id}")


async def broadcast_ingest_progress(payload: dict) -> None:
    await sio_app.emit("ingest:progress", payload)


async def broadcast_match_update(profile_id: str, payload: dict) -> None:
    await sio_app.emit("match:update", payload, room=f"profile:{profile_id}")
