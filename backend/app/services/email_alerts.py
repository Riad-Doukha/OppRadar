"""Email delivery of in-app alerts: scan summaries, match alerts and deadline
reminders that are "sent" in the app and not emailed yet go out in one email (so
a released digest batch becomes one digest email). Honours the email channel and
the alert rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.auth import CurrentUser
from app.models import Me
from app.repositories import Repository
from app.services import mailer

LOOKBACK = timedelta(days=7)  # never email old backlog after turning email on


def deliver(repo: Repository, user: CurrentUser, me: Me) -> int:
    """Email this user's pending alerts; returns how many were included."""
    n = me.notifications
    if me.is_demo or not n.email_enabled:
        return 0
    rules = (
        ("digest", n.rule_new_match),  # the agent's "found N new opportunities" summary
        ("match", n.rule_new_match),
        ("deadline", n.rule_deadline_reminders),
    )
    kinds = [k for k, on in rules if on]
    if not kinds:
        return 0
    since = datetime.now(timezone.utc) - LOOKBACK
    rows = [
        r
        for r in repo.list_notifications(user.id, kinds, since, 50)
        if (r.get("status") or "sent") == "sent" and not r.get("emailed_at")
    ]
    if not rows:
        return 0
    to = user.email or me.email or repo.user_email(user.id)
    if not to:
        return 0
    subject, html = mailer.alert_email(me.locale, user.id, rows)
    if not mailer.send(to, subject, html, user.id):
        return 0  # retried on the next scan
    repo.update_notifications(
        user.id, [str(r["id"]) for r in rows], {"emailed_at": datetime.now(timezone.utc)}
    )
    return len(rows)


def send_test(repo: Repository, user: CurrentUser, me: Me) -> bool:
    to = user.email or me.email or repo.user_email(user.id)
    if not to:
        return False
    subject, html = mailer.test_email(me.locale, user.id)
    return mailer.send(to, subject, html, user.id)
