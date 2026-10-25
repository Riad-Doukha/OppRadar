"""Dashboard endpoints: the signed-in user's opportunity feed and counts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.auth import User, Writer
from app.models import (
    AgentStatus,
    DashboardStats,
    FeedTab,
    MyOpportunity,
    MyOpportunityPage,
    OpportunityTypeName,
    ScanResult,
)
from app.repositories import Repository, get_repository
from app.services import feed

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(user: User, repo: Repo) -> DashboardStats:
    """Counts for the dashboard tiles and tabs."""
    return feed.dashboard(repo, user)


@router.post("/agent/start", response_model=AgentStatus, status_code=status.HTTP_202_ACCEPTED)
def start_agent(user: Writer, repo: Repo) -> AgentStatus:
    """'Start my agent': turn matching on and run the first scan now."""
    return feed.start_agent(repo, user)


@router.post("/agent/scan", response_model=ScanResult)
def scan(user: User, repo: Repo) -> ScanResult:
    """'Run scan now': re-match this profile against every open opportunity."""
    return feed.scan(repo, user)


@router.get("/opportunities", response_model=MyOpportunityPage)
def list_my_opportunities(
    user: User,
    repo: Repo,
    tab: FeedTab = "for_you",
    q: Annotated[str | None, Query(max_length=200)] = None,
    type: Annotated[list[OpportunityTypeName], Query()] = [],  # noqa: B006 - FastAPI query list
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MyOpportunityPage:
    """'For you' (types chosen in onboarding), 'Closing soon' (7 days) or 'Saved'."""
    query = q.strip() if q and q.strip() else None
    return feed.list_feed(repo, user, tab, types=type, q=query, limit=limit, offset=offset)


@router.get("/opportunities/{opportunity_id}", response_model=MyOpportunity)
def get_my_opportunity(user: User, repo: Repo, opportunity_id: UUID) -> MyOpportunity:
    return feed.get_one(repo, user, str(opportunity_id))


@router.put("/opportunities/{opportunity_id}/saved", response_model=MyOpportunity)
def save(user: Writer, repo: Repo, opportunity_id: UUID) -> MyOpportunity:
    return feed.set_flag(repo, user, str(opportunity_id), "saved_at", True)


@router.delete("/opportunities/{opportunity_id}/saved", response_model=MyOpportunity)
def unsave(user: Writer, repo: Repo, opportunity_id: UUID) -> MyOpportunity:
    return feed.set_flag(repo, user, str(opportunity_id), "saved_at", False)


@router.put("/opportunities/{opportunity_id}/dismissed", response_model=MyOpportunity)
def dismiss(user: Writer, repo: Repo, opportunity_id: UUID) -> MyOpportunity:
    """'Not interested': hidden from 'For you' and 'Closing soon'."""
    return feed.set_flag(repo, user, str(opportunity_id), "dismissed_at", True)


@router.delete("/opportunities/{opportunity_id}/dismissed", response_model=MyOpportunity)
def undismiss(user: Writer, repo: Repo, opportunity_id: UUID) -> MyOpportunity:
    return feed.set_flag(repo, user, str(opportunity_id), "dismissed_at", False)
