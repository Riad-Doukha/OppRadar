"""Premium early access (no payments yet)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import User, Writer
from app.models import PremiumStatus, ReservationIn
from app.repositories import Repository, get_repository
from app.services import premium

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("", response_model=PremiumStatus)
def get_status(user: User, repo: Repo) -> PremiumStatus:
    """Current plan (always Free until payments launch) and any early-access reservation."""
    return premium.status(repo, user)


@router.put("/reservation", response_model=PremiumStatus)
def reserve(user: Writer, repo: Repo, body: ReservationIn) -> PremiumStatus:
    """Reserve early access / join the Clubs waitlist. Nothing is charged."""
    return premium.reserve(repo, user, body)


@router.delete("/reservation", response_model=PremiumStatus)
def cancel(user: Writer, repo: Repo) -> PremiumStatus:
    return premium.cancel(repo, user)
