"""Applications page + "I've submitted it" from the Apply assistant."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.auth import User, Writer
from app.models import ApplicationOut, ApplicationPatch
from app.repositories import Repository, get_repository
from app.services import applications

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("", response_model=list[ApplicationOut])
def list_applications(user: User, repo: Repo) -> list[ApplicationOut]:
    return applications.list_for(repo, user)


@router.put("/{opportunity_id}", response_model=ApplicationOut)
def save_application(
    user: Writer, repo: Repo, opportunity_id: UUID, body: ApplicationPatch
) -> ApplicationOut:
    """Create or update the application for an opportunity (status, reference, notes)."""
    return applications.save(repo, user, str(opportunity_id), body)


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(user: Writer, repo: Repo, opportunity_id: UUID) -> Response:
    applications.remove(repo, user, str(opportunity_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
