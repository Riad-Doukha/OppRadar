# Phase 7 end-to-end: the whole product flow in ONE offline walk-through —
# documents -> profile, drop folder + batched ingestion -> opportunities,
# scoring (expired/scam bait dropped) -> matches, rules -> notifications,
# plain-Pydantic rows -> JSON store, and answer() reporting the chat module's
# state. No network: httpx is booby-trapped so any real call fails the test.

from __future__ import annotations

import importlib.util
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from oppradar_ai import api
from oppradar_ai.api import ApiError
from oppradar_ai.config import get_settings
from oppradar_ai.dropfolder import scan_drop_folder
from oppradar_ai.matching import prefs_from_settings
from oppradar_ai.schemas import (
    ChatAnswer,
    Opportunity,
    Profile,
    ScamFlag,
    ScamFlagDetail,
    Source,
)
from oppradar_ai.store import JsonStore

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"

# One structured record the drop folder accepts as-is (no model involved).
DROP_ROW = {
    "title": "Community Grant 2027",
    "organizer": "Open Society Fund",
    "type": "grant",
    "mode": "remote",
    "deadline": "2027-06-01",
    "eligibility": ["Open to students"],
    "summary": "A grant announced via the drop folder.",
    "url": "https://jobs.example.org/community-grant",
}


def test_the_whole_flow_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_network(monkeypatch)
    settings = _offline_settings(tmp_path)
    profile = _step_documents()
    opportunities, matches, notes = _step_pipeline(profile, tmp_path, settings)
    _step_store(tmp_path, profile, opportunities, matches, notes)
    _step_chat(profile)


def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any real HTTP call inside this offline flow is a bug -> hard failure."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("the offline e2e flow attempted a network call")

    monkeypatch.setattr("httpx.Client.request", _boom)
    monkeypatch.setattr("httpx.post", _boom)


def _offline_settings(tmp_path: Path):
    """Throwaway data dir, offline gate, notifications forced deliverable."""
    return get_settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "run_live_llm": False,
            "fetch_delay_seconds": 0.0,
            "notify_threshold": 0.0,
            "quiet_hours_start": 0,
            "quiet_hours_end": 0,
        }
    ).ensure_dirs()


def _drop(folder: Path, name: str, payload: object) -> None:
    """Write a drop file and backdate it past the mid-write guard."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    past = time.time() - 5
    os.utime(path, (past, past))


def _step_documents() -> Profile:
    """The user's files -> one Profile (offline provider, consent route)."""
    profile = api.parse_documents(
        [SAMPLES / "cv_amine.pdf", SAMPLES / "certificate_alx_amine.pdf"],
        user_id="u-e2e",
        kinds=["cv", "certificate"],
        allow_llm=True,
    )
    assert profile.user_id == "u-e2e"
    assert profile.skills and profile.certificates
    return profile


def _step_pipeline(profile: Profile, tmp_path: Path, settings) -> tuple:
    """Drop folder + batched ingestion + single extraction -> scored matches."""
    _drop(settings.live_feed_dir, "grant.json", DROP_ROW)
    drop_report = scan_drop_folder(settings)
    assert len(drop_report.opportunities) == 1

    feed = Source(name="samples", url=str(SAMPLES / "feed_opportunities.xml"), kind="rss")
    report = api.run_ingestion(sources=[feed], settings=settings)
    assert report.items_fetched >= 2
    assert report.extractions.made + report.extractions.cached == 1  # one call per feed

    pasted = api.extract_opportunity(
        text="Spring Grant 2027. Deadline: 1 April 2027. Open to students.",
        settings=settings,
    )
    assert pasted.deadline is not None and pasted.deadline.isoformat() == "2027-04-01"

    expired = Opportunity(
        title="Expired Call", organizer="Org", deadline=date.today() - timedelta(days=1),
        url="https://jobs.example.org/expired",
    )
    fee_call = Opportunity(
        title="Fee Call", organizer="Org", url="https://jobs.example.org/fee",
        scam_flags=[ScamFlagDetail(flag=ScamFlag.APPLICATION_FEE, detail="asks for money")],
    )
    opportunities = [*report.opportunities, *drop_report.opportunities, pasted]
    matches = api.score_user(profile, [*opportunities, expired, fee_call], settings=settings)
    matched = {match.opportunity.id for match in matches}
    assert expired.id not in matched and fee_call.id not in matched
    assert matches == sorted(matches, key=lambda m: -m.score)
    assert all(0.0 <= m.score <= 100.0 and 1 <= len(m.top_reasons) <= 3 for m in matches)

    prefs = prefs_from_settings(profile.user_id, settings).model_copy(update={"threshold": 0.0})
    notes = api.decide_notifications(matches, prefs, [], now=datetime(2026, 1, 1, 12, 0))
    sent = [n for n in notes if n.status.value == "sent"]
    assert 0 < len(sent) <= prefs.daily_cap
    again = api.decide_notifications(matches, prefs, notes, now=datetime(2026, 1, 1, 12, 0))
    assert not any(n.status.value == "sent" for n in again)  # cap + dedupe hold
    return opportunities, matches, notes


def _step_store(
    tmp_path: Path,
    profile: Profile,
    opportunities: list[Opportunity],
    matches: list,
    notes: list,
) -> None:
    """The backend persists our plain Pydantic rows as JSON (no database here)."""
    store = JsonStore(root=tmp_path / "store")
    store.save_opportunities(opportunities)
    assert len(store.list_opportunities()) == len(opportunities)
    store.save_matches(profile.user_id, matches)
    assert store.get_matches(profile.user_id) == matches
    store.add_notifications(notes)
    assert store.notification_history(profile.user_id, limit=50)


def _step_chat(profile: Profile) -> None:
    """answer() proxies the chat module or reports it honestly as unavailable."""
    if importlib.util.find_spec("oppradar_ai.chat") is None:
        with pytest.raises(ApiError) as exc:
            api.answer(profile, None, [], "What is the deadline?")
        assert exc.value.code == "chat-unavailable"
        return
    reply = api.answer(profile, None, [], "What is the deadline?")
    assert isinstance(reply, ChatAnswer)
