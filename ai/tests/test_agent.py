# The background agent, its drop folder and the toast board: one cycle is
# drop folder (+ live ingestion only behind RUN_LIVE_LLM) -> matching ->
# notification rules -> toast callbacks. Everything runs offline with the fake
# provider and the fake embedder; no test here may touch the network.

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from oppradar_ai.agent import BackgroundAgent, status_rows
from oppradar_ai.config import get_settings
from oppradar_ai.dropfolder import scan_drop_folder
from oppradar_ai.schemas import (
    AgentStatus,
    MatchResult,
    Notification,
    NotificationStatus,
    Opportunity,
    Profile,
)
from oppradar_ai.store import JsonStore
from oppradar_ai.toasts import toast_html

AI_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = AI_ROOT / "data" / "fixtures"

# A dropped record the fixture profiles' preferences do not filter out.
DROP_ROW = {
    "title": "Dropped Internship",
    "organizer": "Drop Org",
    "type": "internship",
    "deadline": "2027-06-30",
}


def _settings(tmp_path: Path, **updates: Any):
    """Test configuration: throwaway data dir, offline, notifications forced on."""
    updates.setdefault("data_dir", tmp_path / "data")
    updates.setdefault("run_live_llm", False)
    updates.setdefault("notify_threshold", 0.0)
    updates.setdefault("quiet_hours_start", 0)
    updates.setdefault("quiet_hours_end", 0)
    return get_settings().model_copy(update=updates).ensure_dirs()


def _drop(folder: Path, name: str, payload: Any) -> Path:
    """Write a drop-file and backdate it past the mid-write guard."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    past = time.time() - 5
    os.utime(path, (past, past))
    return path


def _store(tmp_path: Path, *, with_fixtures: bool = False) -> JsonStore:
    """An isolated store, optionally seeded with the committed fixtures."""
    store = JsonStore(root=tmp_path / "store")
    if with_fixtures:
        rows = json.loads((FIXTURES / "profiles.json").read_text(encoding="utf-8"))
        for row in rows:
            store.save_user(Profile.model_validate(row))
        rows = json.loads((FIXTURES / "opportunities.json").read_text(encoding="utf-8"))
        store.save_opportunities([Opportunity.model_validate(row) for row in rows])
    return store


# --------------------------------------------------------------------------- #
# Drop folder
# --------------------------------------------------------------------------- #
def test_json_drop_becomes_a_user_opportunity(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _drop(settings.live_feed_dir, "one.json", DROP_ROW)

    report = scan_drop_folder(settings)

    assert report.scanned == 1
    assert report.consumed == ["one.json"]
    [item] = report.opportunities
    assert item.added_via == "user"
    assert item.source == "drop:one.json"
    assert item.id  # a deterministic slug id, generated from title+url
    assert item.deadline == date(2027, 6, 30)
    assert (settings.live_feed_dir / "consumed" / "one.json").exists()
    assert not (settings.live_feed_dir / "one.json").exists()


def test_json_drop_accepts_a_list_wrapper(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    row = {"title": "Second", "organizer": "Org"}
    _drop(settings.live_feed_dir, "many.json", {"opportunities": [DROP_ROW, row]})

    report = scan_drop_folder(settings)

    assert [item.title for item in report.opportunities] == ["Dropped Internship", "Second"]


def test_html_drop_is_extracted_rules_first(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    html = (
        "<html><head><title>Summer ML Internship 2027</title></head><body><article>"
        "<h1>Summer ML Internship 2027</h1><p>Deadline: December 31, 2026</p>"
        "<p>Join our research team in Algiers to build machine learning models.</p>"
        "</article></body></html>"
    )
    _drop(settings.live_feed_dir, "page.html", html)

    report = scan_drop_folder(settings)

    assert report.consumed == ["page.html"]
    [item] = report.opportunities
    assert item.deadline == date(2026, 12, 31)
    assert item.deadline_source == "rule"  # the rule beats whatever the model said
    assert item.added_via == "user"


def test_broken_json_is_quarantined_and_never_raises(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _drop(settings.live_feed_dir, "broken.json", "{not json at all")

    report = scan_drop_folder(settings)

    assert report.quarantined == ["broken.json"]
    assert report.opportunities == []
    assert any("unreadable JSON" in line for line in report.errors)
    assert (settings.live_feed_dir / "quarantine" / "broken.json").exists()


def test_row_missing_required_fields_is_quarantined(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _drop(settings.live_feed_dir, "no_title.json", {"organizer": "Org"})

    report = scan_drop_folder(settings)

    assert report.quarantined == ["no_title.json"]
    assert report.errors  # the exact field, in one error line


def test_wip_file_is_left_for_the_next_cycle(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = settings.live_feed_dir / "wip.json"
    settings.live_feed_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DROP_ROW), encoding="utf-8")
    future = time.time() + 60  # a file still being written has a fresh mtime
    os.utime(path, (future, future))

    report = scan_drop_folder(settings)

    assert report.skipped == ["wip.json"]
    assert path.exists()


def test_other_files_are_ignored(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _drop(settings.live_feed_dir, "notes.txt", "not a feed")

    report = scan_drop_folder(settings)

    assert report.scanned == 0
    assert (settings.live_feed_dir / "notes.txt").exists()


# --------------------------------------------------------------------------- #
# One cycle: drop -> match -> notify -> toast
# --------------------------------------------------------------------------- #
def test_run_cycle_wires_every_stage_together(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = _store(tmp_path, with_fixtures=True)
    agent = BackgroundAgent(settings=settings, store=store, sources=[])
    toasts: list[tuple[Notification, Any]] = []
    agent.add_notification_callback(lambda note, match: toasts.append((note, match)))
    _drop(settings.live_feed_dir, "one.json", DROP_ROW)

    report = agent.run_cycle()

    assert report.drop is not None and report.drop.consumed == ["one.json"]
    assert report.ingestion is None and "offline" in report.ingestion_skipped
    assert report.items_found == 1
    assert store.get_opportunity(report.drop.opportunities[0].id) is not None
    assert report.matches > 0  # threshold forced to 0.0: every kept match counts
    assert report.notifications_sent >= 1
    assert report.errors == []
    assert len(toasts) == report.notifications_sent
    assert all(note.status is NotificationStatus.SENT for note, _match in toasts)
    assert all(match is not None for _note, match in toasts)

    status = agent.status()
    assert status.cycles_run == 1
    assert status.items_found == 1
    assert status.notifications == report.notifications_sent


def test_second_cycle_never_notifies_twice(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    agent = BackgroundAgent(
        settings=settings, store=_store(tmp_path, with_fixtures=True), sources=[]
    )
    _drop(settings.live_feed_dir, "one.json", DROP_ROW)
    first = agent.run_cycle()
    assert first.notifications_sent >= 1

    second = agent.run_cycle()

    assert second.matches == first.matches  # same store, same scores
    assert second.notifications_sent == 0
    assert second.notifications_suppressed >= first.notifications_sent


def test_a_broken_ingestion_is_reported_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("oppradar_ai.agent.run_ingestion", _boom)
    settings = _settings(tmp_path, run_live_llm=True, llm_provider="gemini")
    agent = BackgroundAgent(settings=settings, store=_store(tmp_path), sources=[])

    report = agent.run_cycle(mode="agent")

    assert any("ingestion" in line for line in report.errors)
    assert agent.status().cycles_run == 1  # the cycle still completed


def test_demo_cycle_never_touches_remote_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demo mode closes the INGESTION gate too, even with RUN_LIVE_LLM=1.

    Regression: the scheduled 10 s ticks used to live-ingest the real feeds
    because _collect() ignored the cycle's mode (3 full ingestions per
    notebook run, 429 quota walls included).
    """
    from oppradar_ai.schemas import IngestionReport

    calls: list[int] = []

    def _spy(*_args: Any, **_kwargs: Any) -> IngestionReport:
        calls.append(1)
        now = datetime.now(timezone.utc)
        return IngestionReport(started_at=now, finished_at=now)

    monkeypatch.setattr("oppradar_ai.agent.run_ingestion", _spy)
    settings = _settings(tmp_path, run_live_llm=True, llm_provider="gemini")
    agent = BackgroundAgent(settings=settings, store=_store(tmp_path), sources=[])

    report = agent.run_cycle(mode="demo")
    assert calls == []  # demo: local drop folder only, whatever the gate says
    assert "offline" in report.ingestion_skipped

    agent.run_cycle(mode="agent")
    assert calls == [1]  # agent mode honors the open gate exactly once


def test_demo_mode_closes_the_gate_agent_mode_honors_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from oppradar_ai.matching import composer

    seen: list[Any] = []
    real = composer.score_user

    def _spy(profile: Profile, opportunities: list[Opportunity], **kwargs: Any) -> Any:
        seen.append(kwargs.get("settings"))
        return real(profile, opportunities, **kwargs)

    monkeypatch.setattr("oppradar_ai.agent.score_user", _spy)
    settings = _settings(tmp_path, run_live_llm=True)
    agent = BackgroundAgent(
        settings=settings, store=_store(tmp_path, with_fixtures=True), sources=[]
    )

    agent.run_cycle(mode="demo")
    assert seen and all(config.run_live_llm is False for config in seen)

    seen.clear()
    agent.run_cycle(mode="agent")
    assert seen and all(config.run_live_llm is True for config in seen)


# --------------------------------------------------------------------------- #
# Scheduler controls + status table
# --------------------------------------------------------------------------- #
def test_start_pause_resume_stop(tmp_path: Path) -> None:
    settings = _settings(tmp_path, demo_interval_seconds=1)
    agent = BackgroundAgent(settings=settings, store=_store(tmp_path), sources=[])

    status = agent.start(mode="demo")
    assert status.state == "running"
    assert status.next_run is not None
    assert agent.start(mode="agent").mode == "demo"  # second start is a no-op

    deadline = time.time() + 10
    while agent.status().cycles_run == 0 and time.time() < deadline:
        time.sleep(0.1)
    assert agent.status().cycles_run >= 1  # the scheduler really ticked

    assert agent.pause().state == "paused"
    assert agent.status().next_run is None
    assert agent.resume().state == "running"
    assert agent.stop().state == "stopped"
    assert agent.status().next_run is None


def test_controls_on_a_stopped_agent_do_not_raise(tmp_path: Path) -> None:
    agent = BackgroundAgent(settings=_settings(tmp_path), store=_store(tmp_path), sources=[])

    assert agent.pause().state == "stopped"
    assert agent.resume().state == "stopped"
    assert agent.stop().state == "stopped"
    assert agent.stop().cycles_run == 0


def test_start_keeps_the_last_cycle_in_the_status_table(tmp_path: Path) -> None:
    """A (re)start changes only the loop's controls, never the table's history.

    Regression: start() used to rebuild AgentStatus and wiped last_run /
    items_found / matches / notifications (cycles_run was kept -> inconsistent
    table: "cycles run: 1" with "last run: -").
    """
    settings = _settings(tmp_path, demo_interval_seconds=3600)
    agent = BackgroundAgent(settings=settings, store=_store(tmp_path), sources=[])
    _drop(settings.live_feed_dir, "one.json", DROP_ROW)
    first = agent.run_cycle()

    agent.start(mode="demo")
    status = agent.status()

    assert status.cycles_run == 1
    assert status.last_run is not None
    assert status.items_found == first.items_found == 1
    agent.stop()


def test_status_rows_show_the_table_the_notebook_displays() -> None:
    labels = [label for label, _ in status_rows(AgentStatus(state="running"))]

    assert labels == [
        "state",
        "mode",
        "interval (s)",
        "last run",
        "next run",
        "items found",
        "matches",
        "notifications",
        "cycles run",
        "last error",
    ]


# --------------------------------------------------------------------------- #
# Toasts
# --------------------------------------------------------------------------- #
def _note_and_match() -> tuple[Notification, MatchResult]:
    opportunity = Opportunity(
        title="ML Intern", organizer="Org", url="https://example.org/ml"
    )
    match = MatchResult(
        profile_id="u",
        opportunity=opportunity,
        score=85.0,
        top_reasons=["Python fits", "Remote friendly"],
    )
    note = Notification(
        profile_id="u",
        opportunity_id=opportunity.title,  # no id yet -> title key
        title=opportunity.title,
        score=85.0,
        deadline=date(2027, 1, 1),
        url=opportunity.url,
    )
    return note, match


def test_toast_html_shows_title_score_reasons_and_link() -> None:
    note, match = _note_and_match()

    html = toast_html(note, match)

    assert "ML Intern" in html
    assert "https://example.org/ml" in html
    assert "85.0/100" in html
    assert "Python fits" in html and "Remote friendly" in html
    assert "2027-01-01" in html


def test_toast_html_falls_back_to_the_single_reason() -> None:
    note, _match = _note_and_match()
    note.reason = "Matches your skills"

    html = toast_html(note)

    assert "Matches your skills" in html


def test_toast_board_pushes_trims_and_clears() -> None:
    widgets = pytest.importorskip("ipywidgets")
    from oppradar_ai.toasts import ToastBoard

    board = ToastBoard(max_visible=2)
    note, _match = _note_and_match()

    board.push(note)
    board.push(note)
    board.push(note)  # over the limit: the oldest toast disappears

    assert len(board.container.children) == 2
    assert len(board.delivered) == 3
    board.clear()
    assert board.container.children == ()
    assert len(board.delivered) == 3  # history survives the visual clear
    assert isinstance(board.container, widgets.VBox)


def test_agent_toast_board_end_to_end(tmp_path: Path) -> None:
    pytest.importorskip("ipywidgets")
    from oppradar_ai.toasts import ToastBoard

    settings = _settings(tmp_path)
    agent = BackgroundAgent(
        settings=settings, store=_store(tmp_path, with_fixtures=True), sources=[]
    )
    board = ToastBoard(max_visible=5)
    agent.add_notification_callback(board.push)
    _drop(settings.live_feed_dir, "one.json", DROP_ROW)

    report = agent.run_cycle()

    assert report.notifications_sent >= 1
    assert len(board.delivered) == report.notifications_sent
    assert all(note.url or note.title for note in board.delivered)
