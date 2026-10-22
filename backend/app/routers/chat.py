"""Ask the agent. Until the AI chat phase ships, answers are look-ups in
OppRadar's own opportunities (see services/chat.py)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.auth import User, Writer
from app.models import ChatHistory, ChatRequest
from app.repositories import Repository, get_repository
from app.services import chat

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("/history", response_model=ChatHistory)
def get_history(user: User, repo: Repo) -> ChatHistory:
    """Past turns, oldest first — empty when the chat-history consent is off."""
    return chat.history(repo, user)


@router.post("", response_model=ChatHistory)
def ask(user: User, repo: Repo, body: ChatRequest) -> ChatHistory:
    """One question -> the new user + assistant turns. Read-only for the demo:
    it answers but stores nothing."""
    return chat.ask(repo, user, body.message)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_history(user: Writer, repo: Repo) -> Response:
    chat.clear(repo, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
