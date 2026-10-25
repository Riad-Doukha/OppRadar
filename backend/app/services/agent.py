"""The agent: runs the AI pipeline (oppradar_ai, via services.ai) and stores
what it finds in Postgres — our database stays the source of truth.

- ingest():      sources -> opportunities (dedupe + scam check), logged as a run
- match_user():  one profile x open opportunities -> matches + match alerts
- run_cycle():   ingest, then re-match everyone whose agent is on (scheduler)

Remote model / web calls happen only when the AI gate is open (RUN_LIVE_LLM=1
with a real provider); otherwise the AI runs on its local rules and samples.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from oppradar_ai.schemas import Notification as AINotification

from app.auth import CurrentUser
from app.models import IngestionRun, OpportunityFilters, ScanResult
from app.repositories import Repository
from app.services import ai, email_alerts, notifications, profiles
from app.sockets.events import push

log = logging.getLogger(__name__)
MAX_OPPORTUNITIES = 500  # matched per user per scan
MANUAL_COOLDOWN = timedelta(minutes=15)  # free tier: no tighter than this from /admin
DAILY_CAP = 5  # instant match alerts per user per day
DIGEST_EVERY = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}
LOCAL = ZoneInfo("Africa/Algiers")  # quiet hours are local time
_cycle_lock = threading.Lock()  # one ingestion at a time (free-tier budget)


class CooldownError(RuntimeError):
    """A manual ingestion ran too recently."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# -- ingestion -------------------------------------------------------------------------- #
def ingest(
    repo: Repository, *, trigger: str = "manual", admin_id: str | None = None
) -> IngestionRun:
    if trigger == "manual":
        last = repo.list_ingestion_runs(1)
        if last:
            started = last[0]["started_at"]
            if isinstance(started, str):
                started = datetime.fromisoformat(started.replace("Z", "+00:00"))
            wait = started + MANUAL_COOLDOWN - _now()
            if wait > timedelta(0):
                minutes = int(wait.total_seconds() // 60) + 1
                raise CooldownError(f"The last run was just now — try again in {minutes} min.")
    if not _cycle_lock.acquire(blocking=False):
        raise RuntimeError("An ingestion run is already in progress.")
    started = _now()
    try:
        report = ai.run_ingestion()
        rows = [ai.opportunity_row(o) for o in report.opportunities]
        saved = repo.upsert_opportunities(rows)
        summary = report.model_dump(mode="json", exclude={"opportunities"})
        row = {
            "trigger": trigger,
            "triggered_by": admin_id,
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "items_fetched": report.items_fetched,
            "items_new": report.items_new,
            "items_saved": saved,
            "items_flagged": report.items_flagged,
            "report": summary,
        }
    except Exception as exc:  # a broken run is logged, never a crash
        log.exception("ingestion failed")
        row = {"trigger": trigger, "triggered_by": admin_id, "started_at": started,
               "finished_at": _now(), "error": str(exc)[:500]}  # fmt: skip
    finally:
        _cycle_lock.release()
    return IngestionRun.model_validate(repo.add_ingestion_run(row))


def runs(repo: Repository, limit: int = 10) -> list[IngestionRun]:
    return [IngestionRun.model_validate(r) for r in repo.list_ingestion_runs(limit)]


# -- matching ----------------------------------------------------------------------------- #
def _open_opportunities(repo: Repository) -> list[dict[str, Any]]:
    rows, _ = repo.list_opportunities(OpportunityFilters(limit=MAX_OPPORTUNITIES))
    return rows


def _match_alerts(repo: Repository, user_id: str) -> list[dict[str, Any]]:
    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    return repo.list_notifications(user_id, ["match"], since, 500)


def _history(rows: list[dict[str, Any]], user_id: str) -> list[AINotification]:
    """Match alerts sent or held — the AI uses them for dedupe and the daily cap."""
    return [
        AINotification(
            profile_id=user_id,
            opportunity_id=str(r["opportunity_id"]),
            title=r["title"],
            score=float(r.get("score") or 0),
            status=r.get("status") or "sent",
            created_at=r["created_at"],
        )
        for r in rows
        if r.get("opportunity_id")
    ]


def _local_day(value: Any) -> date:
    text = value if isinstance(value, datetime) else str(value).replace("Z", "+00:00")
    when = text if isinstance(text, datetime) else datetime.fromisoformat(text)
    return when.astimezone(LOCAL).date()


def _quiet(now: datetime, start: int, end: int) -> bool:
    h = now.hour
    return start != end and (start <= h < end if start < end else h >= start or h < end)


def _release(
    repo: Repository,
    user_id: str,
    rows: list[dict[str, Any]],
    settings: dict[str, Any],
    now: datetime,
) -> int:
    """Turn held alerts into sent ones once their reason is over (the AI queues
    them; delivering them later is ours)."""
    held = sorted(
        (r for r in rows if r.get("status") == "pending"), key=lambda r: str(r["created_at"])
    )
    if not held:
        return 0
    frequency = settings.get("frequency", "instant")
    if frequency in DIGEST_EVERY:
        oldest = held[0]["created_at"]
        if isinstance(oldest, str):
            oldest = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
        if now - oldest < DIGEST_EVERY[frequency]:
            return 0
        ids = [str(r["id"]) for r in held]
    else:
        prefs = ai.notification_prefs(user_id, settings)
        if _quiet(now, prefs.quiet_hours_start, prefs.quiet_hours_end):
            return 0
        today = now.date()
        sent_today = sum(
            1 for r in rows if r.get("status") == "sent" and _local_day(r["created_at"]) == today
        )  # fmt: skip
        ids = [str(r["id"]) for r in held][: max(0, DAILY_CAP - sent_today)]
    repo.update_notifications(
        user_id, ids, {"status": "sent", "suppressed_reason": None, "created_at": now}
    )
    return len(ids)


def match_user(
    repo: Repository, user: CurrentUser, rows: list[dict[str, Any]] | None = None
) -> ScanResult:
    """Score this user's profile against every open opportunity, store the
    matches and send the alerts their settings allow."""
    me = profiles.load_me(repo, user)
    rows = _open_opportunities(repo) if rows is None else rows
    by_id = {str(r["id"]): r for r in rows}
    results = ai.score(ai.to_ai_profile(me), [ai.opportunity_from_row(r) for r in rows])
    repo.replace_matches(
        user.id,
        [
            {
                "opportunity_id": m.opportunity.id,
                "score": round(m.score, 2),
                "semantic_similarity": round(m.semantic_similarity, 3),
                "bonus": round(m.bonus, 3),
                "criteria": [c.model_dump(mode="json") for c in m.criteria],
                "top_reasons": m.top_reasons,
                "unmet_requirements": m.unmet_requirements,
                "reasons_source": m.reasons_source,
            }
            for m in results
            if m.opportunity.id in by_id
        ],
    )

    sent = 0
    if not me.is_demo and me.notifications.rule_new_match:
        settings = me.notifications.model_dump()
        prefs = ai.notification_prefs(user.id, settings)
        now = datetime.now(LOCAL)
        alerts = _match_alerts(repo, user.id)
        sent += _release(repo, user.id, alerts, settings, now)
        for note in ai.decide_notifications(results, prefs, _history(alerts, user.id), now):
            if note.status == "suppressed" or note.opportunity_id not in by_id:
                continue  # suppressed = already notified (dedupe)
            added = repo.add_notification(
                {
                    "user_id": user.id,
                    "kind": "match",
                    "title": f"{round(note.score)}% match — {note.title}",
                    "body": note.reason,
                    "reason": note.reason,
                    "score": note.score,
                    "deadline": note.deadline,
                    "url": note.url,
                    "mode": note.mode.value if hasattr(note.mode, "value") else note.mode,
                    "status": note.status.value if hasattr(note.status, "value") else note.status,
                    "suppressed_reason": note.suppressed_reason,
                    "opportunity_id": note.opportunity_id,
                    "action_url": f"/opportunities/{note.opportunity_id}",
                    "dedupe_key": f"match:{note.opportunity_id}",
                }
            )
            sent += added is not None and added.get("status") == "sent"
        notifications.invalidate(user.id)
        if sent:
            push(user.id, "notification:new", {"kind": "match", "count": sent})
        email_alerts.deliver(repo, user, me)
    return ScanResult(
        matches=len(results), notifications_sent=sent, scanned=len(rows), finished_at=_now()
    )


def match_everyone(repo: Repository) -> int:
    rows = _open_opportunities(repo)
    done = 0
    for user_id in repo.agent_user_ids():
        try:
            match_user(repo, CurrentUser(id=user_id), rows)
            done += 1
        except Exception:  # one profile must not stop the others
            log.exception("matching failed for %s", user_id)
    return done


def run_cycle(repo: Repository) -> IngestionRun:
    """Scheduled job: fetch new opportunities, then re-match every active agent."""
    run = ingest(repo, trigger="scheduled")
    matched = match_everyone(repo)
    log.info("agent cycle: %s new opportunities, %s profiles matched", run.items_new, matched)
    purge(repo)
    return run


CHAT_KEEP = timedelta(days=90)  # promised on /privacy
APPLICATIONS_KEEP = timedelta(days=365)  # the "12 months" history setting


def purge(repo: Repository) -> tuple[int, int]:
    """Delete chat and application history past its retention period."""
    now = datetime.now(timezone.utc)
    chat, applications = repo.purge_expired(now - CHAT_KEEP, now - APPLICATIONS_KEEP)
    if chat or applications:
        log.info("retention: deleted %s chat messages, %s applications", chat, applications)
    return chat, applications
