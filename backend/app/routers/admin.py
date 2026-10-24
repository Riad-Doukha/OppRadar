"""Admin area: review queue, flagged sources, and opportunity management.
Admins are users whose app_metadata.role is "admin" (scripts/make_admin.py)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.auth import Admin
from app.models import (
    AdminOpportunityIn,
    AdminStats,
    IngestionRun,
    OpportunityPatch,
    ReviewedOpportunity,
    ReviewedOpportunityPage,
    ReviewIn,
    TrustLevelName,
)
from app.repositories import Repository, get_repository
from app.services import agent, review

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("/stats", response_model=AdminStats)
def stats(_: Admin, repo: Repo) -> AdminStats:
    return review.stats(repo)


@router.post("/ingest", response_model=IngestionRun)
def ingest(admin: Admin, repo: Repo) -> IngestionRun:
    """Run the AI ingestion now (sources -> extraction -> dedupe -> scam check),
    then re-match every active agent. Remote calls need the AI gate open."""
    try:
        run = agent.ingest(repo, trigger="manual", admin_id=admin.id)
    except agent.CooldownError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    agent.match_everyone(repo)
    return run


@router.get("/ingest/runs", response_model=list[IngestionRun])
def ingestion_runs(
    _: Admin, repo: Repo, limit: Annotated[int, Query(ge=1, le=50)] = 10
) -> list[IngestionRun]:
    return agent.runs(repo, limit)


@router.get("/opportunities", response_model=ReviewedOpportunityPage)
def list_opportunities(
    _: Admin,
    repo: Repo,
    status_: Annotated[
        list[Literal["pending", "approved", "rejected"]], Query(alias="status")
    ] = [],  # noqa: B006 - FastAPI query list
    trust: Annotated[list[TrustLevelName], Query()] = [],  # noqa: B006
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewedOpportunityPage:
    """Every opportunity, whatever its review status, newest first."""
    return review.list_for_admin(
        repo, list(status_), list(trust), (q or "").strip() or None, limit, offset
    )


@router.post(
    "/opportunities", response_model=ReviewedOpportunity, status_code=status.HTTP_201_CREATED
)
def create(admin: Admin, repo: Repo, body: AdminOpportunityIn) -> ReviewedOpportunity:
    """Add an opportunity by hand (published right away)."""
    return review.create(repo, admin, body)


@router.get("/opportunities/{opportunity_id}", response_model=ReviewedOpportunity)
def get(_: Admin, repo: Repo, opportunity_id: UUID) -> ReviewedOpportunity:
    return review.get(repo, str(opportunity_id))


@router.patch("/opportunities/{opportunity_id}", response_model=ReviewedOpportunity)
def update(
    _: Admin, repo: Repo, opportunity_id: UUID, body: OpportunityPatch
) -> ReviewedOpportunity:
    """Edit fields, including the trust level (re-label a suspicious source)."""
    return review.update(repo, str(opportunity_id), body)


@router.post("/opportunities/{opportunity_id}/review", response_model=ReviewedOpportunity)
def decide(admin: Admin, repo: Repo, opportunity_id: UUID, body: ReviewIn) -> ReviewedOpportunity:
    """Approve (publish) or reject; the submitter is notified."""
    return review.review(repo, admin, str(opportunity_id), body)


@router.delete("/opportunities/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(_: Admin, repo: Repo, opportunity_id: UUID) -> Response:
    """Delete for good (saves and tracked applications of it go too)."""
    review.delete(repo, str(opportunity_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
