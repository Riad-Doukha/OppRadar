# Phase 7 contract: api.py exposes the frozen six-function interface (plain
# Pydantic in/out, no database), plus the behaviour of each function offline:
# rules-only document parsing, gated URL extraction, ApiError codes, and the
# chat module reporting itself honestly until the chat branch lands.

from __future__ import annotations

import importlib.util
import inspect
from datetime import datetime
from pathlib import Path

import pytest

from oppradar_ai import api
from oppradar_ai.api import ApiError, detect_kind, extract_opportunity, parse_documents
from oppradar_ai.schemas import (
    ChatAnswer,
    ChatTurn,
    Opportunity,
    Profile,
)

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"

# name -> (positional params, keyword-only params, return annotation)
_CONTRACT: dict[str, tuple[list[str], list[str], str]] = {
    "parse_documents": (["files"], ["user_id", "kinds", "allow_llm"], "Profile"),
    "run_ingestion": (["sources"], ["settings"], "IngestionReport"),
    "extract_opportunity": (
        ["url", "text", "image"], ["source_name", "settings"], "Opportunity"
    ),
    "score_user": (
        ["profile", "opportunities"], ["settings", "today"], "list[MatchResult]"
    ),
    "decide_notifications": (
        ["matches", "prefs", "history"], ["now"], "list[Notification]"
    ),
    "answer": (
        ["profile", "opportunity", "history", "message"], ["settings"], "ChatAnswer"
    ),
}


# --------------------------------------------------------------------------- #
# The frozen contract
# --------------------------------------------------------------------------- #
def test_contract_signatures_are_frozen() -> None:
    for name, (positional, keyword_only, returns) in _CONTRACT.items():
        fn = getattr(api, name)
        params = list(inspect.signature(fn).parameters.values())
        kinds = [p.kind for p in params]
        assert kinds.count(inspect.Parameter.VAR_POSITIONAL) == 0, name
        assert kinds.count(inspect.Parameter.VAR_KEYWORD) == 0, name
        assert [p.name for p in params if p.kind is p.POSITIONAL_OR_KEYWORD] == positional, name
        assert [p.name for p in params if p.kind is p.KEYWORD_ONLY] == keyword_only, name
        assert str(inspect.signature(fn).return_annotation) == returns, name


def test_api_error_carries_a_machine_readable_code() -> None:
    assert ApiError("nope", code="empty").code == "empty"
    assert ApiError("nope").code == "api_error"


# --------------------------------------------------------------------------- #
# parse_documents
# --------------------------------------------------------------------------- #
def test_parse_documents_rejects_empty_input() -> None:
    with pytest.raises(ApiError) as exc:
        parse_documents([])
    assert exc.value.code == "empty"


def test_parse_documents_rejects_unknown_kinds() -> None:
    with pytest.raises(ApiError) as exc:
        parse_documents([SAMPLES / "cv_amine.pdf"], kinds=["passport"])
    assert exc.value.code == "arguments"


def test_parse_documents_default_route_invents_nothing() -> None:
    """Rules-only: contact details from regexes, never LLM-canned skills."""
    profile = parse_documents([SAMPLES / "cv_amine.pdf"], user_id="u-api")
    assert profile.user_id == "u-api"
    assert profile.source_files == ["cv_amine.pdf"]
    assert profile.skills == []  # no invented content without consent


def test_parse_documents_allow_llm_route_uses_the_provider() -> None:
    profile = parse_documents([SAMPLES / "cv_amine.pdf"], allow_llm=True)
    assert profile.skills  # the (fake, offline) provider filled the schema


def test_parse_documents_merges_kinds_with_explicit_labels() -> None:
    profile = parse_documents(
        [SAMPLES / "cv_amine.pdf", SAMPLES / "certificate_alx_amine.pdf"],
        kinds=["cv", "certificate"],
        allow_llm=True,
    )
    assert len(profile.source_files) == 2
    assert profile.certificates  # the certificate landed in its own section


def test_parse_documents_survives_one_broken_file() -> None:
    broken = SAMPLES / "feed_opportunities.xml"  # unsupported extension for reader
    profile = parse_documents([SAMPLES / "cv_amine.pdf", broken])
    assert profile.source_files == ["cv_amine.pdf"]


def test_parse_documents_unreadable_only_raises_api_error() -> None:
    with pytest.raises(ApiError) as exc:
        parse_documents([SAMPLES / "feed_opportunities.xml"])
    assert exc.value.code == "unreadable"


def test_detect_kind_heuristic() -> None:
    assert detect_kind("Certificate of completion, 2024") == "certificate"
    assert detect_kind("Certificat de reussite") == "certificate"
    assert detect_kind("My portfolio of projects") == "portfolio"
    assert detect_kind("Amine, data student, a@b.com") == "cv"


# --------------------------------------------------------------------------- #
# extract_opportunity
# --------------------------------------------------------------------------- #
def test_extract_opportunity_needs_exactly_one_source() -> None:
    for kwargs in ({}, {"text": "x", "url": "https://jobs.example.org/j"}):
        with pytest.raises(ApiError) as exc:
            extract_opportunity(**kwargs)
        assert exc.value.code == "arguments"


def test_extract_opportunity_from_pasted_text() -> None:
    opp = extract_opportunity(
        text="DAAD Scholarship 2027. Deadline: 15 March 2027. Apply now."
    )
    assert isinstance(opp, Opportunity)
    assert opp.deadline is not None and opp.deadline.isoformat() == "2027-03-15"
    assert opp.deadline_source == "rule"  # the source's line, never a guess


def test_extract_opportunity_rejects_a_listicle() -> None:
    with pytest.raises(ApiError) as exc:
        extract_opportunity(text="Top 10 Scholarships in Europe for 2026")
    assert exc.value.code == "rejected"
    assert "listicle" in str(exc.value)


def test_extract_opportunity_html_is_cleaned_first() -> None:
    html = (
        "<html><body><h1>Spring Grant</h1>"
        "<p>Deadline: 1 April 2027. Open to students.</p></body></html>"
    )
    opp = extract_opportunity(text=html)
    assert opp.deadline is not None and opp.deadline.isoformat() == "2027-04-01"


def test_extract_opportunity_url_is_refused_offline() -> None:
    """RUN_LIVE_LLM unset -> the URL route fails loudly instead of fetching."""
    with pytest.raises(ApiError) as exc:
        extract_opportunity(url="https://jobs.example.org/j")
    assert exc.value.code == "offline"


def test_extract_opportunity_pending_when_the_budget_is_spent() -> None:
    from oppradar_ai.config import get_settings

    settings = get_settings().model_copy(update={"max_extractions_per_run": 0})
    with pytest.raises(ApiError) as exc:
        extract_opportunity(text="A call with no budget left.", settings=settings)
    assert exc.value.code == "pending"


def test_extract_opportunity_unusable_when_the_extractor_has_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from oppradar_ai.ingestion.extract import RawExtraction

    monkeypatch.setattr(
        "oppradar_ai.api.extract_record",
        lambda *a, **k: RawExtraction(url=k.get("url", "")),
    )
    with pytest.raises(ApiError) as exc:
        extract_opportunity(text="whatever")
    assert exc.value.code == "unusable"


def test_extract_opportunity_image_route_uses_the_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from oppradar_ai.schemas import DocumentContent

    monkeypatch.setattr(
        "oppradar_ai.api.read_document",
        lambda path: DocumentContent(
            file_name="announcement.png", method="image_ocr", text="Spring Grant."
        ),
    )
    opp = extract_opportunity(image="announcement.png")
    assert isinstance(opp, Opportunity)


# --------------------------------------------------------------------------- #
# run_ingestion / score_user / decide_notifications
# --------------------------------------------------------------------------- #
def test_run_ingestion_with_no_sources_returns_an_empty_report() -> None:
    report = api.run_ingestion(sources=[])
    assert report.items_new == 0 and report.failures == []


def test_score_user_orders_matches_best_first() -> None:
    from oppradar_ai.config import get_settings

    profile = Profile(
        user_id="u-api", skills=["python"], languages=["english"],
        country="Algeria", summary="Student.",
    )
    opps = [
        Opportunity(title=f"Opportunity {i}", organizer="Org", url=f"https://jobs.example.org/{i}")
        for i in range(3)
    ]
    matches = api.score_user(profile, opps, settings=get_settings())
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= score <= 100.0 for score in scores)
    assert all(1 <= len(m.top_reasons) <= 3 for m in matches)


def test_decide_notifications_respects_threshold_and_dedupe(sample_match) -> None:
    from oppradar_ai.matching import prefs_from_settings

    prefs = prefs_from_settings(sample_match.profile_id).model_copy(
        update={"threshold": 70.0}
    )
    now = datetime(2026, 1, 1, 12, 0)
    first = api.decide_notifications([sample_match], prefs, [], now=now)
    assert first and first[0].status.value == "sent"
    second = api.decide_notifications([sample_match], prefs, first, now=now)
    assert second and second[0].status.value == "suppressed"  # already delivered


# --------------------------------------------------------------------------- #
# answer()
# --------------------------------------------------------------------------- #
def test_answer_reports_the_chat_module_state() -> None:
    profile = Profile(user_id="u-api", skills=["python"], summary="Student.")
    if importlib.util.find_spec("oppradar_ai.chat") is None:
        with pytest.raises(ApiError) as exc:
            api.answer(profile, None, [ChatTurn(role="user", content="hi")], "Deadline?")
        assert exc.value.code == "chat-unavailable"
    else:  # the chat branch has landed: the wrapper must proxy and validate
        reply = api.answer(profile, None, [], "Deadline?")
        assert isinstance(reply, ChatAnswer)
