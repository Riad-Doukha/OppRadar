"""Opportunity endpoints — public browse/search.

Rows come from the ingestion pipeline (not shipped yet) or, until then, from
`python scripts/seed.py` (the AI fixtures). Admin review and the organisation
submission form arrive with the opportunities UI phase.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.models import (
    OpportunityFilters,
    OpportunityOut,
    OpportunityPage,
    OpportunityTypeName,
    TrustLevelName,
)
from app.repositories import NotFoundError, Repository, get_repository

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("", response_model=OpportunityPage)
def list_opportunities(
    repo: Repo,
    q: Annotated[str | None, Query(max_length=200, description="Full-text search")] = None,
    type: Annotated[list[OpportunityTypeName], Query()] = [],  # noqa: B006 - FastAPI query list
    mode: Annotated[list[Literal["remote", "hybrid", "onsite"]], Query()] = [],  # noqa: B006
    country: Annotated[str | None, Query(max_length=60)] = None,
    trust: Annotated[list[TrustLevelName], Query()] = [],  # noqa: B006
    include_expired: bool = False,
    deadline_before: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OpportunityPage:
    filters = OpportunityFilters(
        q=q.strip() if q and q.strip() else None,
        types=type,
        modes=mode,
        country=country,
        trust_levels=trust,
        include_expired=include_expired,
        deadline_before=deadline_before,
        limit=limit,
        offset=offset,
    )
    rows, total = repo.list_opportunities(filters)
    return OpportunityPage(
        items=[OpportunityOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(repo: Repo, opportunity_id: UUID) -> Any:
    row = repo.get_opportunity(str(opportunity_id))
    if row is None:
        raise NotFoundError(f"opportunity {opportunity_id}")
    return row
