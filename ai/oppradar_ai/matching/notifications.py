# Notification rules: threshold, daily cap, quiet hours, digest mode and the
# "never twice for the same user + opportunity" rule — one pure decision
# function. Called by: api.py (Phase 7), the agent, notebooks. Persisting and
# sending stay in store.py / the agent, never here.

from __future__ import annotations

import logging
from datetime import date, datetime

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.schemas import (
    MatchResult,
    Notification,
    NotificationMode,
    NotificationPrefs,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


def prefs_from_settings(profile_id: str, settings: Settings | None = None) -> NotificationPrefs:
    """Delivery preferences of one user, straight from the configuration.

    Example:
        >>> prefs_from_settings("u-amine").daily_cap
        5
    """
    settings = settings or get_settings()
    return NotificationPrefs(
        profile_id=profile_id,
        mode=settings.digest_mode,  # "daily"/"weekly" is mapped to DIGEST by the schema
        daily_cap=settings.daily_instant_cap,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        threshold=settings.notify_threshold,
    )


def decide_notifications(
    matches: list[MatchResult],
    prefs: NotificationPrefs,
    history: list[Notification],
    *,
    now: datetime | None = None,
) -> list[Notification]:
    """Matches -> notifications: threshold, cap, quiet hours, digest, no duplicates.

    Rows keep the matches' order; a match below the threshold is not a
    notification at all. Suppressed rows are returned too, so the user can always
    see *why* something did not reach them (callers persist only what they want).

    Example:
        >>> notes = decide_notifications(matches, prefs, [], now=datetime(2026, 1, 1, 12))
        >>> [n.status.value for n in notes]
        ['sent', 'pending']
    """
    now = now or datetime.now().astimezone()
    today = _local_date(now)
    sent_today = _sent_on(history, prefs.profile_id, today)
    decided: list[Notification] = []
    for match in matches:
        if match.score < prefs.threshold:
            continue
        status, why = _status_of(match, prefs, history, sent_today, now)
        decided.append(_notification(match, prefs, status, why, now))
        if status is NotificationStatus.SENT:
            sent_today += 1
    logger.info(
        "%d/%d matches became notifications for %s (%d sent, %d deferred, %d suppressed)",
        len(decided),
        len(matches),
        prefs.profile_id,
        sum(1 for n in decided if n.status is NotificationStatus.SENT),
        sum(1 for n in decided if n.status is NotificationStatus.PENDING),
        sum(1 for n in decided if n.status is NotificationStatus.SUPPRESSED),
    )
    return decided


def in_quiet_hours(now: datetime, start: int, end: int) -> bool:
    """True between start and end (22-8 crosses midnight; equal hours mean never).

    Example:
        >>> in_quiet_hours(datetime(2026, 1, 1, 23, 30), 22, 8)
        True
        >>> in_quiet_hours(datetime(2026, 1, 1, 8, 0), 22, 8)
        False
        >>> in_quiet_hours(datetime(2026, 1, 1, 12, 0), 22, 22)
        False
    """
    if start == end:
        return False
    if start > end:  # wraps midnight, e.g. 22 -> 8
        return now.hour >= start or now.hour < end
    return start <= now.hour < end


def _notification(
    match: MatchResult,
    prefs: NotificationPrefs,
    status: NotificationStatus,
    why: str | None,
    now: datetime,
) -> Notification:
    """One row: everything the UI needs, keyed by id (or url/title when absent)."""
    opportunity = match.opportunity
    return Notification(
        profile_id=prefs.profile_id,
        opportunity_id=opportunity.id or opportunity.url or opportunity.title,
        title=opportunity.title,
        reason=match.top_reasons[0] if match.top_reasons else "",
        score=match.score,
        deadline=opportunity.deadline,
        url=opportunity.url,
        mode=prefs.mode,
        status=status,
        suppressed_reason=why,
        created_at=now,
    )


def _status_of(
    match: MatchResult,
    prefs: NotificationPrefs,
    history: list[Notification],
    sent_today: int,
    now: datetime,
) -> tuple[NotificationStatus, str | None]:
    """The delivery rules, in the only order that makes sense: dedupe first."""
    if _already_notified(history, prefs.profile_id, _opportunity_key(match)):
        return NotificationStatus.SUPPRESSED, "already notified for this opportunity"
    if prefs.mode is NotificationMode.DIGEST:
        return NotificationStatus.PENDING, "digest mode: queued with the next digest"
    if in_quiet_hours(now, prefs.quiet_hours_start, prefs.quiet_hours_end):
        return (
            NotificationStatus.PENDING,
            f"quiet hours {prefs.quiet_hours_start:02d}-{prefs.quiet_hours_end:02d}: deferred",
        )
    if sent_today >= prefs.daily_cap:
        why = f"daily cap {prefs.daily_cap} reached: deferred to tomorrow"
        return NotificationStatus.PENDING, why
    return NotificationStatus.SENT, None


def _opportunity_key(match: MatchResult) -> str:
    """Dedupe key: the id, or the url/title when the listing has no id yet."""
    opportunity = match.opportunity
    return opportunity.id or opportunity.url or opportunity.title


def _already_notified(history: list[Notification], profile_id: str, opportunity_id: str) -> bool:
    """Sent or queued before -> never again (suppressed rows do not count)."""
    return any(
        row.profile_id == profile_id
        and row.opportunity_id == opportunity_id
        and row.status in (NotificationStatus.SENT, NotificationStatus.PENDING)
        for row in history
    )


def _sent_on(history: list[Notification], profile_id: str, day: date) -> int:
    """How many notifications this user already got on that (local) day."""
    return sum(
        1
        for row in history
        if row.profile_id == profile_id
        and row.status is NotificationStatus.SENT
        and _local_date(row.created_at) == day
    )


def _local_date(moment: datetime) -> date:
    """The local date of a timestamp (aware values converted, naive used as-is)."""
    return moment.astimezone().date() if moment.tzinfo else moment.date()
