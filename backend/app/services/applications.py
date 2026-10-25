"""Applications the user tracks: recorded from the Apply assistant ("I've
submitted it") and updated on the Applications page. The agent will create
and update these itself once the AI form-filling phase ships."""

from __future__ import annotations

from datetime import datetime, timezone

from app.auth import CurrentUser
from app.models import ApplicationOut, ApplicationPatch, OpportunityFilters
from app.repositories import Repository
from app.services import notifications
from app.services.parallel import gather


def list_for(repo: Repository, user: CurrentUser) -> list[ApplicationOut]:
    apps = repo.list_applications(user.id)
    if not apps:
        return []
    ids = [str(a["opportunity_id"]) for a in apps]
    rows, _ = repo.list_opportunities(OpportunityFilters(ids=ids, include_expired=True, limit=100))
    by_id = {str(r["id"]): r for r in rows}
    return [
        ApplicationOut.model_validate({**a, "opportunity": by_id.get(str(a["opportunity_id"]))})
        for a in apps
    ]


def save(
    repo: Repository, user: CurrentUser, opportunity_id: str, body: ApplicationPatch
) -> ApplicationOut:
    r = gather(
        existing=lambda: next(
            (
                a
                for a in repo.list_applications(user.id)
                if str(a["opportunity_id"]) == opportunity_id
            ),
            None,
        ),
        opportunity=lambda: repo.get_opportunity(opportunity_id),
    )
    fields = body.model_dump(exclude_unset=True)
    status = fields.get("status") or (r["existing"] or {}).get("status") or "submitted"
    fields["status"] = status
    first_submit = status == "submitted" and not (r["existing"] or {}).get("submitted_at")
    if first_submit:
        fields["submitted_at"] = datetime.now(timezone.utc)
    row = repo.upsert_application(user.id, opportunity_id, fields)

    if first_submit and r["opportunity"]:
        ref = row.get("reference")
        repo.add_notification(
            {
                "user_id": user.id,
                "kind": "application",
                "title": f"Application recorded — {r['opportunity']['title']}",
                "body": (f"Reference {ref}. " if ref else "")
                + "Update its status on the Applications page when you hear back.",
                "opportunity_id": opportunity_id,
                "action_url": "/applications",
                "dedupe_key": f"application:{opportunity_id}:submitted",
            }
        )
        notifications.invalidate(user.id)
    return ApplicationOut.model_validate({**row, "opportunity": r["opportunity"]})


def remove(repo: Repository, user: CurrentUser, opportunity_id: str) -> None:
    repo.delete_application(user.id, opportunity_id)
