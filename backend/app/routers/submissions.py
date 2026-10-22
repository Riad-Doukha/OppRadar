"""Organisation submissions: anyone with an account can propose an
opportunity; it goes public only after an admin approves it."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth import User, Writer
from app.models import ReviewedOpportunity, SubmissionIn
from app.repositories import Repository, get_repository
from app.services import review

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.post("", response_model=ReviewedOpportunity, status_code=status.HTTP_201_CREATED)
def submit(user: Writer, repo: Repo, body: SubmissionIn) -> ReviewedOpportunity:
    """Submit an opportunity for review (at most 5 waiting per account)."""
    return review.submit(repo, user, body)


@router.get("", response_model=list[ReviewedOpportunity])
def mine(user: User, repo: Repo) -> list[ReviewedOpportunity]:
    """Your submissions with their review status and the admin's note."""
    return review.mine(repo, user)
