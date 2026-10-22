"""OppRadar FastAPI application."""

import logging

import socketio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.repositories import NotFoundError
from app.routers import (
    applications,
    auth,
    chat,
    documents,
    feed,
    health,
    matches,
    me,
    notifications,
    opportunities,
    premium,
)
from app.services.ai import LLMError
from app.sockets import sio_app

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

app = FastAPI(
    title="OppRadar API",
    version="0.2.0",
    description="Backend for OppRadar — opportunities in, matches out.",
)


@app.middleware("http")
async def unexpected_errors(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Turn crashes into a JSON 500 *inside* the CORS middleware (registered
    after this, so it wraps it). Otherwise Starlette answers from the outermost
    layer without CORS headers and the browser only reports "Failed to fetch"."""
    try:
        return await call_next(request)
    except Exception:
        logging.getLogger("app").exception(
            "unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            {"detail": "Something went wrong on our side. Please try again."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse({"detail": "Not found."}, status_code=status.HTTP_404_NOT_FOUND)


@app.exception_handler(LLMError)
async def ai_unavailable(_: Request, exc: LLMError) -> JSONResponse:
    return JSONResponse(
        {"detail": "The AI service is unavailable right now. Please try again shortly."},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


app.include_router(health.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(me.router, prefix="/me", tags=["me"])
app.include_router(feed.router, prefix="/me", tags=["dashboard"])
app.include_router(notifications.router, prefix="/me/notifications", tags=["notifications"])
app.include_router(applications.router, prefix="/me/applications", tags=["applications"])
app.include_router(premium.router, prefix="/me/premium", tags=["premium"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

# Socket.IO (live document/ingestion/match updates). Clients connect to the
# backend origin with `path: "/ws/socket.io"`.
# Starlette keeps the full path in mounted sub-apps, so the engine must know it.
app.mount("/ws", socketio.ASGIApp(sio_app, socketio_path="ws/socket.io"))
