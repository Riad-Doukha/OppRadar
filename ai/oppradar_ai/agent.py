# Background agent: one scheduled loop — drop folder + (live) ingestion ->
# matching -> notification rules — on APScheduler's thread. AGENT_INTERVAL_SECONDS
# (1 h) normally, DEMO_INTERVAL_SECONDS (10 s) in demo mode. Every cycle is
# wrapped: a broken source, store or toast callback is recorded in the report and
# the loop keeps running — the notebook kernel can never be taken down by it.
# Called by: notebooks/08_background_agent, api.py (Phase 7).

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.dropfolder import scan_drop_folder
from oppradar_ai.ingestion.pipeline import run_ingestion
from oppradar_ai.matching import decide_notifications, prefs_from_settings, score_user
from oppradar_ai.schemas import (
    AgentCycleReport,
    AgentStatus,
    MatchResult,
    Notification,
    NotificationStatus,
    Source,
)
from oppradar_ai.store import JsonStore

logger = logging.getLogger(__name__)

# What a toast listener receives: the SENT notification and the match behind it.
NotificationCallback = Callable[[Notification, MatchResult | None], None]


class BackgroundAgent:
    """The scheduled loop: ingest -> match -> notify, without ever crashing.

    Example:
        >>> agent = BackgroundAgent(sources=[])      # local-only cycle
        >>> report = agent.run_cycle()
        >>> agent.status().state
        'stopped'
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        store: JsonStore | None = None,
        sources: list[Source] | None = None,
    ) -> None:
        self.settings = (settings or get_settings()).ensure_dirs()
        self.store = store or JsonStore()
        self.sources = sources  # None = load sources.yaml on every live cycle
        self._callbacks: list[NotificationCallback] = []
        self._scheduler: BackgroundScheduler | None = None
        self._lock = threading.Lock()
        self._status = AgentStatus()
        self.last_cycle: AgentCycleReport | None = None

    # -- controls ------------------------------------------------------------- #
    def start(self, mode: Literal["demo", "agent"] = "demo") -> AgentStatus:
        """Start the loop: `demo` ticks every DEMO_INTERVAL_SECONDS, `agent`
        every AGENT_INTERVAL_SECONDS. Starting twice is a no-op, never a crash.

        Example:
            >>> agent = BackgroundAgent(sources=[])          # doctest: +SKIP
            >>> agent.start("demo").state
            'running'
        """
        with self._lock:
            if self._scheduler is not None:
                logger.warning("start() ignored: agent already %s", self._status.state)
                return self.status()
            interval = self._interval(mode)
            self._scheduler = BackgroundScheduler(timezone=None)  # local time
            self._scheduler.add_job(
                self._cycle_job,
                IntervalTrigger(seconds=interval),
                id="oppradar-cycle",
                coalesce=True,  # missed ticks collapse into one run
                max_instances=1,  # a slow cycle never overlaps its successor
                misfire_grace_time=max(int(interval), 1),
            )
            self._scheduler.start()
            # Keep the last cycle's numbers: a (re)start changes only the
            # loop's control fields, never the status table's history.
            self._status.state = "running"
            self._status.mode = mode
            self._status.interval_seconds = interval
            self._status.started_at = datetime.now(timezone.utc)
        logger.info("agent started: %s mode, every %s s", mode, interval)
        return self.status()

    def pause(self) -> AgentStatus:
        """Pause the loop; nothing fires until resume() (schedule kept)."""
        if self._scheduler is None:
            logger.warning("pause() ignored: the agent is stopped")
            return self.status()
        self._scheduler.pause_job("oppradar-cycle")
        self._status.state = "paused"
        self._status.next_run = None
        logger.info("agent paused")
        return self.status()

    def resume(self) -> AgentStatus:
        """Resume a paused loop (the next tick fires on the original cadence)."""
        if self._scheduler is None:
            logger.warning("resume() ignored: the agent is stopped")
            return self.status()
        self._scheduler.resume_job("oppradar-cycle")
        self._status.state = "running"
        self._status.next_run = self._next_run()
        logger.info("agent resumed")
        return self.status()

    def stop(self) -> AgentStatus:
        """Stop the loop for good; a later start() builds a fresh scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._status.state = "stopped"
        self._status.next_run = None
        logger.info("agent stopped after %d cycle(s)", self._status.cycles_run)
        return self.status()

    def status(self) -> AgentStatus:
        """A snapshot of the status table (last run, next run, counts)."""
        self._status.next_run = self._next_run() if self._status.state == "running" else None
        return self._status.model_copy(deep=True)

    def add_notification_callback(self, callback: NotificationCallback) -> None:
        """Register a listener, called for every SENT notification per cycle."""
        self._callbacks.append(callback)

    # -- the cycle ------------------------------------------------------------ #
    def run_cycle(self, *, mode: Literal["demo", "agent"] | None = None) -> AgentCycleReport:
        """One full cycle: drop folder -> (live) ingestion -> matching -> rules.

        Never raises: every failure lands in the report's `errors`. A demo
        cycle never touches the network at all — no feeds, no model calls, no
        phrasing; only the agent mode honors RUN_LIVE_LLM as configured.
        """
        mode = mode or self._status.mode
        started = datetime.now(timezone.utc)
        report = AgentCycleReport(started_at=started, finished_at=started, mode=mode)
        with self._lock:
            self._collect(report, mode)
            self._match_and_notify(report, mode)
            report.finished_at = datetime.now(timezone.utc)
            self.last_cycle = report
            self._roll_up(report)
        return report

    def _cycle_job(self) -> None:
        """The scheduled entry point: whatever happens, the loop survives."""
        try:
            self.run_cycle()
        except Exception:  # pragma: no cover - run_cycle already catches everything
            logger.exception("agent cycle crashed outside the report")

    # -- stages --------------------------------------------------------------- #
    def _collect(self, report: AgentCycleReport, mode: str) -> None:
        """Drop folder (always local) + remote ingestion (agent mode + gate)."""
        try:
            report.drop = scan_drop_folder(self.settings)
            report.errors.extend(report.drop.errors)  # broken files belong here too
        except Exception as exc:
            report.errors.append(f"drop folder: {exc}")
            logger.exception("drop folder scan failed")
        try:
            if self._remote_allowed(mode):
                report.ingestion = run_ingestion(sources=self.sources, settings=self.settings)
            else:
                report.ingestion_skipped = (
                    "offline: RUN_LIVE_LLM is closed or the provider is fake — "
                    "remote sources untouched this cycle"
                )
        except Exception as exc:
            report.errors.append(f"ingestion: {exc}")
            logger.exception("ingestion failed")
        self._store_fresh(report)

    def _store_fresh(self, report: AgentCycleReport) -> None:
        """Upsert this cycle's finds into the store; failures become errors."""
        fresh = list(report.drop.opportunities if report.drop else [])
        if report.ingestion:
            fresh.extend(report.ingestion.opportunities)
        try:
            self.store.save_opportunities(fresh)
        except Exception as exc:
            report.errors.append(f"store: {exc}")
            logger.exception("saving new opportunities failed")
        report.items_found = len(fresh)

    def _match_and_notify(self, report: AgentCycleReport, mode: str) -> None:
        """Score every stored profile, apply the rules, persist, toast SENT."""
        opportunities = self.store.list_opportunities()
        scoring = self._scoring_settings(mode)
        for profile in self.store.list_users():
            try:
                matches = score_user(profile, opportunities, settings=scoring)
                self.store.save_matches(profile.user_id, matches)
                prefs = prefs_from_settings(profile.user_id, self.settings)
                notes = decide_notifications(
                    matches, prefs, self.store.notification_history(profile.user_id)
                )
                self.store.add_notifications(notes)
                self._count(report, matches, notes, prefs.threshold)
                self._fire(matches, notes)
            except Exception as exc:
                report.errors.append(f"matching {profile.user_id}: {exc}")
                logger.exception("matching failed for %s", profile.user_id)

    def _scoring_settings(self, mode: str) -> Settings:
        """Demo closes the model gate for scoring: a 10 s loop must never spend
        the free tier. The hourly agent mode honors RUN_LIVE_LLM as configured."""
        if mode == "demo":
            return self.settings.model_copy(update={"run_live_llm": False})
        return self.settings

    def _remote_allowed(self, mode: str) -> bool:
        """Remote ingestion needs BOTH the agent mode AND the same opt-in as
        everywhere else (RUN_LIVE_LLM=1 with a real provider). A demo cycle —
        the 10 s loop, or any cycle after stop() — never touches the network:
        that is what keeps the public feeds safe and the free tier unspent."""
        return (
            mode == "agent"
            and self.settings.run_live_llm
            and self.settings.llm_provider != "fake"
        )

    def _count(
        self,
        report: AgentCycleReport,
        matches: list[MatchResult],
        notes: list[Notification],
        threshold: float,
    ) -> None:
        """Tally one profile's contribution to the cycle's status numbers."""
        report.matches += sum(1 for m in matches if m.score >= threshold)
        for note in notes:
            if note.status is NotificationStatus.SENT:
                report.notifications_sent += 1
            elif note.status is NotificationStatus.PENDING:
                report.notifications_pending += 1
            else:
                report.notifications_suppressed += 1

    def _fire(self, matches: list[MatchResult], notes: list[Notification]) -> None:
        """Toast callbacks for SENT rows only; a dead widget never kills a cycle."""
        by_key = {
            m.opportunity.id or m.opportunity.url or m.opportunity.title: m for m in matches
        }
        for note in notes:
            if note.status is not NotificationStatus.SENT:
                continue
            match = by_key.get(note.opportunity_id)
            for callback in self._callbacks:
                try:
                    callback(note, match)
                except Exception:
                    logger.exception("notification callback failed; the cycle continues")

    def _roll_up(self, report: AgentCycleReport) -> None:
        """Fold the finished cycle into the status table."""
        self._status.last_run = report.finished_at
        self._status.items_found = report.items_found
        self._status.matches = report.matches
        self._status.notifications = report.notifications_sent
        self._status.cycles_run += 1
        self._status.last_error = report.errors[0] if report.errors else ""
        if self._status.state == "running":
            self._status.next_run = self._next_run()

    # -- helpers --------------------------------------------------------------- #
    def _interval(self, mode: str) -> float:
        if mode == "demo":
            return float(self.settings.demo_interval_seconds)
        return float(self.settings.agent_interval_seconds)

    def _next_run(self) -> datetime | None:
        if self._scheduler is None:
            return None
        job = self._scheduler.get_job("oppradar-cycle")
        return job.next_run_time if job else None


def status_rows(status: AgentStatus) -> list[tuple[str, str]]:
    """The status table as (label, value) rows, ready for display or printing.

    Example:
        >>> labels = [label for label, _ in status_rows(AgentStatus())]
        >>> labels[:3]
        ['state', 'mode', 'interval (s)']
    """
    return [
        ("state", status.state),
        ("mode", status.mode),
        ("interval (s)", f"{status.interval_seconds:g}"),
        ("last run", _stamp(status.last_run)),
        ("next run", _stamp(status.next_run)),
        ("items found", str(status.items_found)),
        ("matches", str(status.matches)),
        ("notifications", str(status.notifications)),
        ("cycles run", str(status.cycles_run)),
        ("last error", status.last_error or "-"),
    ]


def _stamp(moment: datetime | None) -> str:
    """Local HH:MM:SS of an aware timestamp, or '-' when absent."""
    return moment.astimezone().strftime("%H:%M:%S") if moment else "-"
