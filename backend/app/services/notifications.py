"""In-app notifications: the bell, the Notifications page, and the kinds the
web app can create on its own before the AI notifier ships.

Created here (idempotent through dedupe_key, honouring Settings → Notifications):
  - deadline: a saved opportunity closes within DEADLINE_DAYS
  - tip:      at most one per ISO week while the profile is incomplete
  - system:   "your agent is set up" after Start my agent
Match / application / digest rows are written by the AI pipeline into the
same table and simply show up here.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone

from app.auth import CurrentUser
from app.models import NotificationList, NotificationOut, NotificationTab, OpportunityFilters
from app.repositories import Repository
from app.repositories.base import Row
from app.services.parallel import gather

DEADLINE_DAYS = 3
KEEP_DAYS = 30  # "Older notifications auto-archive after 30 days"
SYNC_EVERY_S = 300  # the bell asks on every page; don't recompute each time

TAB_KINDS: dict[NotificationTab, list[str] | None] = {
    "all": None,
    "matches": ["match"],
    "deadlines": ["deadline"],
    "applications": ["application"],
    "system": ["digest", "tip", "security", "system"],
}

_last_sync: dict[str, float] = {}
_sync_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _since() -> datetime:
    return _now() - timedelta(days=KEEP_DAYS)


def _out(row: Row) -> NotificationOut:
    return NotificationOut.model_validate({**row, "read": row.get("read_at") is not None})


def invalidate(user_id: str) -> None:
    """Something that can create a notification changed (saved an opportunity,
    started the agent, changed alert rules): recompute on the next read."""
    with _sync_lock:
        _last_sync.pop(user_id, None)


def sync(repo: Repository, user: CurrentUser, *, force: bool = False) -> None:
    """Create any due deadline / tip / system notifications for this user."""
    if user.is_demo:
        return  # read-only account: nothing is written
    with _sync_lock:
        if not force and time.monotonic() - _last_sync.get(user.id, 0) < SYNC_EVERY_S:
            return
        _last_sync[user.id] = time.monotonic()

    r = gather(
        settings=lambda: repo.get_notification_settings(user.id),
        profile=lambda: repo.get_profile(user.id) or {},
        states=lambda: repo.list_opportunity_states(user.id),
    )
    settings, profile, states = r["settings"], r["profile"], r["states"]

    if settings.get("rule_deadline_reminders", True):
        saved = [
            s["opportunity_id"] for s in states if s.get("saved_at") and not s.get("dismissed_at")
        ]
        if saved:
            rows, _ = repo.list_opportunities(
                OpportunityFilters(
                    ids=saved,
                    deadline_before=date.today() + timedelta(days=DEADLINE_DAYS),
                    limit=50,
                )
            )
            for o in rows:
                _deadline(repo, user.id, o)

    pct = round((profile.get("completeness") or 0) * 100)
    if settings.get("rule_profile_tips") and profile.get("onboarding_completed_at") and pct < 100:
        year, week, _ = date.today().isocalendar()
        repo.add_notification(
            {
                "user_id": user.id,
                "kind": "tip",
                "title": "Profile tip — complete your profile to improve matching",
                "body": (
                    f"Your profile is {pct}% complete. Links, experience and skill levels "
                    "help the agent judge eligibility."
                ),
                "action_url": "/profile",
                "dedupe_key": f"tip:{year}-W{week:02d}",
            }
        )

    if profile.get("agent_started_at"):
        repo.add_notification(
            {
                "user_id": user.id,
                "kind": "system",
                "title": "Your agent is set up",
                "body": (
                    "Matching launches soon. Alerts will arrive here and through the "
                    "channels you chose."
                ),
                "action_url": "/settings?tab=notifications",
                "dedupe_key": "system:agent_started",
            }
        )


def _deadline(repo: Repository, user_id: str, o: Row) -> None:
    deadline = (
        o["deadline"] if isinstance(o["deadline"], date) else date.fromisoformat(str(o["deadline"]))
    )
    days = (deadline - date.today()).days
    left = "closes today" if days == 0 else "1 day left" if days == 1 else f"{days} days left"
    repo.add_notification(
        {
            "user_id": user_id,
            "kind": "deadline",
            "title": f"Closing soon: {o['title']} — {left}",
            "body": f"You saved it. Applications close {deadline.strftime('%d %b %Y')}.",
            "opportunity_id": str(o["id"]),
            "deadline": deadline.isoformat(),
            "action_url": f"/opportunities/{o['id']}",
            "dedupe_key": f"deadline:{o['id']}",
        }
    )


def list_tab(
    repo: Repository, user: CurrentUser, tab: NotificationTab, limit: int = 50
) -> NotificationList:
    sync(repo, user)
    since = _since()
    r = gather(
        rows=lambda: repo.list_notifications(user.id, TAB_KINDS[tab], since, limit),
        unread=lambda: repo.count_unread_notifications(user.id, since),
    )
    return NotificationList(items=[_out(n) for n in r["rows"]], unread=r["unread"])


def mark_read(repo: Repository, user: CurrentUser, ids: list[str] | None) -> NotificationList:
    repo.mark_notifications_read(user.id, ids)
    return list_tab(repo, user, "all", limit=5)


def dismiss(repo: Repository, user: CurrentUser, notification_id: str) -> None:
    repo.dismiss_notification(user.id, notification_id)
