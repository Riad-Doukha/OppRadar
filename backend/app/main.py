"""OppRadar FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, health, matches, opportunities, profiles
from app.sockets import sio_app

settings = get_settings()

app = FastAPI(
    title="OppRadar API",
    version="0.1.0",
    description="Backend for OppRadar — opportunities in, matches out.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

# WebSocket namespace (live ingestion/match updates) mounted under /ws.
app.mount("/ws", sio_app)
