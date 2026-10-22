"""The signed-in user's view of opportunities: dashboard tabs, counts, and
Save / Not interested.

Until the AI matcher ships, "For you" means: open opportunities of the types
chosen in onboarding, minus the ones marked "Not interested", soonest
deadline first. Scores and eligibility will be joined here from
public.matches once they exist.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.auth import CurrentUser
from app.models import (
    AgentStatus,
    DashboardStats,
    FeedTab,
    MyOpportunity,
    MyOpportunityPage,
    OpportunityFilters,
    OpportunityTypeName,
)
from app.repositories import NotFoundError, Repository
from app.repositories.base import Row
from app.services import notifications
from app.services.parallel import gather

CLOSING_SOON_DAYS = 7
NEW_FOR = timedelta(days=3)  # "New" badge on cards


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _states(repo: Repository, user_id: str) -> dict[str, Row]:
    return {s["opportunity_id"]: s for s in repo.list_opportunity_states(user_id)}


def _ids(states: dict[str, Row], flag: str) -> list[str]:
    return [oid for oid, s in states.items() if s.get(flag)]


def _filters(
    tab: FeedTab,
    states: dict[str, Row],
    profile: Row,
    *,
    types: list[OpportunityTypeName] | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> OpportunityFilters:
    dismissed = _ids(states, "dismissed_at")
    if tab == "saved":
        # Saved items stay visible even after their deadline passes.
        return OpportunityFilters(
            q=q, types=types or [], ids=_ids(states, "saved_at"), include_expired=True,
            limit=limit, offset=offset,
        )  # fmt: skip
    if tab == "closing":
        return OpportunityFilters(
            q=q, types=types or [], exclude_ids=dismissed,
            deadline_before=date.today() + timedelta(days=CLOSING_SOON_DAYS),
            limit=limit, offset=offset,
        )  # fmt: skip
    wanted = profile.get("opportunity_types") or []
    # An explicit type filter narrows the profile's types (or replaces them if none set).
    chosen = [t for t in (types or wanted) if not wanted or t in wanted] if types else wanted
    return OpportunityFilters(q=q, types=chosen, exclude_ids=dismissed, limit=limit, offset=offset)


def _context(repo: Repository, user: CurrentUser) -> tuple[dict[str, Row], Row]:
    """This user's saved/dismissed state and profile, fetched concurrently."""
    r = gather(
        states=lambda: _states(repo, user.id),
        profile=lambda: repo.get_profile(user.id) or {},
    )
    return r["states"], r["profile"]


def _decorate(row: Row, states: dict[str, Row]) -> MyOpportunity:
    state = states.get(str(row["id"]), {})
    created = row.get("created_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    return MyOpportunity.model_validate(
        {
            **row,
            "saved": bool(state.get("saved_at")),
            "dismissed": bool(state.get("dismissed_at")),
            "is_new": bool(created and _now() - created < NEW_FOR),
        }
    )


def list_feed(
    repo: Repository,
    user: CurrentUser,
    tab: FeedTab,
    *,
    types: list[OpportunityTypeName] | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> MyOpportunityPage:
    states, profile = _context(repo, user)
    filters = _filters(tab, states, profile, types=types, q=q, limit=limit, offset=offset)
    rows, total = repo.list_opportunities(filters)
    return MyOpportunityPage(
        tab=tab,
        items=[_decorate(r, states) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_one(repo: Repository, user: CurrentUser, opportunity_id: str) -> MyOpportunity:
    r = gather(
        row=lambda: repo.get_opportunity(opportunity_id), states=lambda: _states(repo, user.id)
    )
    if r["row"] is None:
        raise NotFoundError(f"opportunity {opportunity_id}")
    return _decorate(r["row"], r["states"])


def set_flag(
    repo: Repository, user: CurrentUser, opportunity_id: str, flag: str, on: bool
) -> MyOpportunity:
    fields: dict[str, Any] = {flag: _now() if on else None}
    if flag == "dismissed_at" and on:
        fields["saved_at"] = None  # "Not interested" also un-saves
    repo.set_opportunity_state(user.id, opportunity_id, fields)
    notifications.invalidate(user.id)  # a saved deadline may need a reminder now
    return get_one(repo, user, opportunity_id)


def dashboard(repo: Repository, user: CurrentUser) -> DashboardStats:
    states, profile = _context(repo, user)

    def count(tab: FeedTab, **extra: Any) -> int:
        filters = _filters(tab, states, profile, limit=1).model_copy(update=extra)
        return repo.list_opportunities(filters)[1]

    counts = gather(
        for_you=lambda: count("for_you"),
        closing_this_week=lambda: count("closing"),
        saved=lambda: count("saved"),
        new_today=lambda: count("for_you", created_after=_now() - timedelta(days=1)),
    )
    return DashboardStats(**counts, agent_started_at=profile.get("agent_started_at"))


def start_agent(repo: Repository, user: CurrentUser) -> AgentStatus:
    """Record that the user started their agent. The scan itself needs the AI
    ingestion + matching phases; until then the status says so."""
    profile = repo.ensure_profile(user.id, user.full_name)
    started = profile.get("agent_started_at")
    if not started:
        started = repo.update_profile(user.id, {"agent_started_at": _now()})["agent_started_at"]
    notifications.invalidate(user.id)
    return AgentStatus(status="waiting_for_matcher", agent_started_at=started)
