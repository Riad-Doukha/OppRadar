"""In-app notifications: the header bell and the Notifications page."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.auth import User, Writer
from app.models import NotificationList, NotificationTab, ReadRequest
from app.repositories import Repository, get_repository
from app.services import notifications

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("", response_model=NotificationList)
def list_notifications(
    user: User,
    repo: Repo,
    tab: NotificationTab = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationList:
    """Last 30 days, newest first, plus the unread count (the bell uses limit=5)."""
    return notifications.list_tab(repo, user, tab, limit)


@router.post("/read", response_model=NotificationList)
def mark_read(user: Writer, repo: Repo, body: ReadRequest) -> NotificationList:
    """Mark the given notifications read, or all of them when `ids` is omitted."""
    ids = [str(i) for i in body.ids] if body.ids is not None else None
    return notifications.mark_read(repo, user, ids)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(user: Writer, repo: Repo, notification_id: UUID) -> Response:
    notifications.dismiss(repo, user, str(notification_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
