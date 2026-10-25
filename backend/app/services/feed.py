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
    ScanResult,
)
from app.repositories import NotFoundError, Repository
from app.repositories.base import Row
from app.services import agent, notifications
from app.services.parallel import gather

CLOSING_SOON_DAYS = 7
NEW_FOR = timedelta(days=3)  # "New" badge on cards
MAX_MATCHED = 500  # "For you" = the matched set, sorted by score


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


def _matches(repo: Repository, user_id: str) -> dict[str, Row]:
    return {str(m["opportunity_id"]): m for m in repo.get_matches(user_id)}


def _context(repo: Repository, user: CurrentUser) -> tuple[dict[str, Row], Row, dict[str, Row]]:
    """This user's saved/dismissed state, profile and AI matches, fetched concurrently."""
    r = gather(
        states=lambda: _states(repo, user.id),
        profile=lambda: repo.get_profile(user.id) or {},
        matches=lambda: _matches(repo, user.id),
    )
    return r["states"], r["profile"], r["matches"]


def _match_info(m: Row | None) -> dict[str, Any] | None:
    if not m:
        return None
    keys = ("score", "top_reasons", "unmet_requirements", "criteria", "reasons_source")
    return {k: m[k] for k in keys if m.get(k) is not None}


def _decorate(
    row: Row, states: dict[str, Row], matches: dict[str, Row] | None = None
) -> MyOpportunity:
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
            "match": _match_info((matches or {}).get(str(row["id"]))),
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
    states, profile, matches = _context(repo, user)
    if tab == "for_you" and matches:
        # Once the agent has scanned: the matched opportunities, best score first.
        filters = OpportunityFilters(
            q=q, types=types or [], ids=list(matches), exclude_ids=_ids(states, "dismissed_at"),
            limit=MAX_MATCHED,
        )  # fmt: skip
        rows, _ = repo.list_opportunities(filters)
        rows.sort(key=lambda r: -float(matches[str(r["id"])]["score"]))
        total, rows = len(rows), rows[offset : offset + limit]
    else:
        filters = _filters(tab, states, profile, types=types, q=q, limit=limit, offset=offset)
        rows, total = repo.list_opportunities(filters)
    return MyOpportunityPage(
        tab=tab,
        items=[_decorate(r, states, matches) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_one(repo: Repository, user: CurrentUser, opportunity_id: str) -> MyOpportunity:
    r = gather(
        row=lambda: repo.get_opportunity(opportunity_id),
        states=lambda: _states(repo, user.id),
        matches=lambda: _matches(repo, user.id),
    )
    if r["row"] is None:
        raise NotFoundError(f"opportunity {opportunity_id}")
    return _decorate(r["row"], r["states"], r["matches"])


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
    states, profile, matches = _context(repo, user)

    def count(tab: FeedTab, **extra: Any) -> int:
        filters = _filters(tab, states, profile, limit=1).model_copy(update=extra)
        if tab == "for_you" and matches:
            dismissed = _ids(states, "dismissed_at")
            filters = filters.model_copy(
                update={"types": [], "ids": list(matches), "exclude_ids": dismissed}
            )
        return repo.list_opportunities(filters)[1]

    counts = gather(
        for_you=lambda: count("for_you"),
        closing_this_week=lambda: count("closing"),
        saved=lambda: count("saved"),
        new_today=lambda: count("for_you", created_after=_now() - timedelta(days=1)),
        applications=lambda: len(repo.list_applications(user.id)),
    )
    return DashboardStats(
        **counts,
        agent_started_at=profile.get("agent_started_at"),
        matching_available=bool(profile.get("agent_started_at")),
        matched=len(matches),
        last_scan_at=max((m["created_at"] for m in matches.values()), default=None),
    )


def start_agent(repo: Repository, user: CurrentUser) -> AgentStatus:
    """Turn the user's agent on and run the first scan right away; after that the
    scheduled cycle re-matches them whenever new opportunities arrive."""
    profile = repo.ensure_profile(user.id, user.full_name)
    started = profile.get("agent_started_at")
    if not started:
        started = repo.update_profile(user.id, {"agent_started_at": _now()})["agent_started_at"]
    scan(repo, user)
    return AgentStatus(status="running", agent_started_at=started)


def scan(repo: Repository, user: CurrentUser) -> ScanResult:
    """ "Run scan now": match this profile against every open opportunity."""
    result = agent.match_user(repo, user)
    notifications.invalidate(user.id)
    return result
