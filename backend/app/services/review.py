"""Organisation submissions and admin review.

Submissions arrive hidden (review_status "pending", trust "unknown") and go
public only when an admin approves them; the submitter gets an in-app
notification either way. Admins can also add, edit, re-label (trust level)
and delete any opportunity. The AI ingestion pipeline keeps writing through
upsert_opportunities, unaffected by this.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.models import (
    AdminOpportunityIn,
    AdminStats,
    OpportunityPatch,
    ReviewedOpportunity,
    ReviewedOpportunityPage,
    ReviewIn,
    SubmissionIn,
)
from app.repositories import NotFoundError, Repository
from app.services import notifications
from app.services.parallel import gather

MAX_PENDING_PER_USER = 5
FLAGGED = ["suspicious", "scam"]


def _out(row: dict) -> ReviewedOpportunity:
    return ReviewedOpportunity.model_validate(row)


# -- organisations ------------------------------------------------------------------ #
def submit(repo: Repository, user: CurrentUser, body: SubmissionIn) -> ReviewedOpportunity:
    _, pending = repo.review_list(["pending"], [], None, user.id, 1, 0)
    if pending >= MAX_PENDING_PER_USER:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You already have {MAX_PENDING_PER_USER} submissions waiting for review.",
        )
    row = repo.create_opportunity(
        {
            **body.model_dump(),
            "source": "form",
            "added_via": "form",
            "trust_level": "unknown",
            "review_status": "pending",
            "submitted_by": user.id,
        }
    )
    repo.add_notification(
        {
            "user_id": user.id,
            "kind": "system",
            "title": f"Submission received — {row['title']}",
            "body": "An admin will review it before it appears in OppRadar. "
            "You can follow its status on the Submit page.",
            "action_url": "/submit",
            "dedupe_key": f"submission:{row['id']}:received",
        }
    )
    notifications.invalidate(user.id)
    return _out(row)


def mine(repo: Repository, user: CurrentUser) -> list[ReviewedOpportunity]:
    rows, _ = repo.review_list([], [], None, user.id, 50, 0)
    return [_out(r) for r in rows]


# -- admins ------------------------------------------------------------------------- #
def stats(repo: Repository) -> AdminStats:
    r = gather(
        pending=lambda: repo.count_opportunities(["pending"], []),
        flagged=lambda: repo.count_opportunities(["approved"], FLAGGED),
        published=lambda: repo.count_opportunities(["approved"], [], active_only=True),
        rejected=lambda: repo.count_opportunities(["rejected"], []),
    )
    return AdminStats(**r)


def list_for_admin(
    repo: Repository,
    statuses: list[str],
    trust_levels: list[str],
    q: str | None,
    limit: int,
    offset: int,
) -> ReviewedOpportunityPage:
    rows, total = repo.review_list(statuses, trust_levels, q, None, limit, offset)
    return ReviewedOpportunityPage(
        items=[_out(r) for r in rows], total=total, limit=limit, offset=offset
    )


def get(repo: Repository, opportunity_id: str) -> ReviewedOpportunity:
    row = repo.get_opportunity_any(opportunity_id)
    if row is None:
        raise NotFoundError(f"opportunity {opportunity_id}")
    return _out(row)


def create(repo: Repository, admin: CurrentUser, body: AdminOpportunityIn) -> ReviewedOpportunity:
    row = repo.create_opportunity(
        {
            **body.model_dump(),
            "source": "admin",
            "added_via": "user",
            "review_status": "approved",
            "reviewed_at": datetime.now(timezone.utc),
            "reviewed_by": admin.id,
        }
    )
    return _out(row)


def update(repo: Repository, opportunity_id: str, body: OpportunityPatch) -> ReviewedOpportunity:
    fields = body.model_dump(exclude_unset=True)
    # Clearing optional fields is allowed (deadline, mode, funding = null);
    # required ones can't be blanked.
    for required in ("title", "organizer", "type", "url", "language", "trust_level"):
        if required in fields and fields[required] is None:
            fields.pop(required)
    if not fields:
        return get(repo, opportunity_id)
    return _out(repo.update_opportunity(opportunity_id, fields))


def review(
    repo: Repository, admin: CurrentUser, opportunity_id: str, body: ReviewIn
) -> ReviewedOpportunity:
    current = get(repo, opportunity_id)
    fields: dict = {
        "review_status": body.status,
        "review_note": body.note or None,
        "reviewed_at": datetime.now(timezone.utc),
        "reviewed_by": admin.id,
    }
    if body.trust_level:
        fields["trust_level"] = body.trust_level
    elif body.status == "approved" and current.trust_level == "unknown":
        # An admin looked at it: no longer "not verified yet".
        fields["trust_level"] = "likely_safe"
    row = repo.update_opportunity(opportunity_id, fields)

    submitter = current.submitted_by and str(current.submitted_by)
    if submitter and current.review_status != body.status:
        approved = body.status == "approved"
        repo.add_notification(
            {
                "user_id": submitter,
                "kind": "system",
                "title": (
                    f"Published — {current.title}"
                    if approved
                    else f"Not published — {current.title}"
                ),
                "body": body.note
                or (
                    "Your submission is now visible to students on OppRadar."
                    if approved
                    else "An admin reviewed your submission and didn't publish it."
                ),
                "opportunity_id": opportunity_id if approved else None,
                "action_url": f"/opportunities/{opportunity_id}" if approved else "/submit",
                "dedupe_key": f"submission:{opportunity_id}:{body.status}",
            }
        )
        notifications.invalidate(submitter)
    return _out(row)


def delete(repo: Repository, opportunity_id: str) -> None:
    repo.delete_opportunity(opportunity_id)
