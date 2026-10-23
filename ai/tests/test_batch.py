# Phase 7 batching: N feed entries per single LLM call (the free-tier fix),
# index-mapped replies, rule-first deadlines per entry, and the
# pending-never-fake guarantee when a call fails or answers short.

from pathlib import Path
from uuid import uuid4

import pytest

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.batch import BatchInput, chunk_prompt, extract_records_batch
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.pipeline import run_ingestion
from oppradar_ai.schemas import OpportunityBatchExtraction, OpportunityExtraction, Source

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def _settings(**updates):
    updates.setdefault("fetch_delay_seconds", 0.0)
    return get_settings().model_copy(update=updates)


def _inputs(count: int, tag: str = "") -> list[BatchInput]:
    """Unique texts per test: the shared disk cache must not leak across tests."""
    unique = tag or uuid4().hex[:8]
    return [
        BatchInput(
            text=f"Entry {unique}-{i}: Deadline: 1 April 2027. Apply now.",
            url=f"https://jobs.univ-annaba.dz/{unique}/{i}",
            title_hint=f"Entry {i}",
        )
        for i in range(count)
    ]


class _StubLLM:
    """Minimal LLM stand-in returning a fixed batch reply (no cache, no call)."""

    name = "stub"
    last_call = None

    def __init__(self, reply: OpportunityBatchExtraction) -> None:
        self.reply = reply

    def is_cached(self, prompt, schema, system=None) -> bool:
        return False

    def structured(self, prompt, schema, system=None) -> OpportunityBatchExtraction:
        return self.reply


# --------------------------------------------------------------------------- #
# One call per chunk
# --------------------------------------------------------------------------- #
def test_three_entries_cost_one_llm_call() -> None:
    budget = RunBudget(_settings())
    outcomes = extract_records_batch(_inputs(3), budget=budget, settings=_settings())
    assert len(outcomes) == 3
    assert budget.extractions.made == 1  # vs 3 calls before batching


def test_batch_items_map_back_by_index_with_distinct_ids() -> None:
    outcomes = extract_records_batch(_inputs(3), settings=_settings())
    ids = [out.opportunity.id for out in outcomes if out.opportunity]
    assert len(ids) == 3
    assert len(set(ids)) == 3  # item numbers keep ids distinct inside one batch


def test_budget_spans_chunks() -> None:
    settings = _settings(extraction_batch_size=2)
    budget = RunBudget(settings, max_extractions=2)
    outcomes = extract_records_batch(_inputs(5), budget=budget, settings=settings)
    assert budget.extractions.made == 2  # chunks 1+2 spent the cap...
    assert budget.extractions.skipped == 1  # ...chunk 3 was declined
    assert sum(1 for out in outcomes if out.pending) == 1  # its entry waits
    assert sum(1 for out in outcomes if out.opportunity) == 4


def test_cached_batch_costs_nothing_on_the_next_run() -> None:
    settings = _settings()
    inputs = _inputs(3, tag="cache-check")
    first = RunBudget(settings)
    extract_records_batch(inputs, budget=first, settings=settings)
    second = RunBudget(settings)
    extract_records_batch(inputs, budget=second, settings=settings)
    assert first.extractions.made == 1
    assert second.extractions.made == 0 and second.extractions.cached == 1


# --------------------------------------------------------------------------- #
# Per-entry rules are unchanged inside a batch
# --------------------------------------------------------------------------- #
def test_listicle_block_is_rejected_inside_a_batch() -> None:
    inputs = _inputs(2)
    inputs[1] = BatchInput(
        text="Top 10 Scholarships of 2026 ranked list.", url="https://example.org/x"
    )
    outcomes = extract_records_batch(inputs, settings=_settings())
    assert outcomes[0].opportunity is not None
    assert outcomes[1].rejected_reason is not None
    assert "listicle" in outcomes[1].rejected_reason


def test_rule_deadline_beats_the_model_inside_a_batch() -> None:
    outcomes = extract_records_batch(_inputs(1), settings=_settings())
    opp = outcomes[0].opportunity
    assert opp is not None
    assert opp.deadline.isoformat() == "2027-04-01"  # the source's line, not March 15
    assert opp.deadline_source == "rule"
    assert any("mismatch" in note for note in opp.review_notes)


def test_budgetless_call_makes_the_whole_chunk_pending() -> None:
    settings = _settings()
    outcomes = extract_records_batch(
        _inputs(3), budget=RunBudget(settings, max_extractions=0), settings=settings
    )
    assert all(out.opportunity is None and out.pending for out in outcomes)
    assert all("budget" in out.pending.reason for out in outcomes)


def test_short_reply_leaves_uncovered_entries_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = OpportunityBatchExtraction(items=[OpportunityExtraction(title="Only One")])
    monkeypatch.setattr("oppradar_ai.ingestion.batch.get_llm", lambda: _StubLLM(reply))
    outcomes = extract_records_batch(_inputs(3), settings=_settings())
    assert outcomes[0].opportunity is not None
    assert sum(1 for out in outcomes if out.pending) == 2
    assert "covered 1 of 3" in outcomes[1].pending.reason


def test_extra_reply_items_are_dropped_never_invented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = OpportunityBatchExtraction(
        items=[OpportunityExtraction(title=f"Extra {i}") for i in range(3)]
    )
    monkeypatch.setattr("oppradar_ai.ingestion.batch.get_llm", lambda: _StubLLM(reply))
    outcomes = extract_records_batch(_inputs(2), settings=_settings())
    assert len(outcomes) == 2  # the extra item never becomes an extra record


# --------------------------------------------------------------------------- #
# Prompt construction + pipeline integration
# --------------------------------------------------------------------------- #
def test_chunk_prompt_caps_every_entry() -> None:
    settings = _settings(llm_max_input_chars=2000, extraction_batch_size=2)
    long_text = "Apply today for the scholarship of your life. " * 100  # ~4500 chars
    inputs = [BatchInput(text=long_text, url="https://jobs.univ-annaba.dz/long")] * 2
    prompt = chunk_prompt(inputs, settings)
    assert prompt.count("=== ITEM ") == 2
    assert "[...truncated...]" in prompt
    assert len(prompt) <= 2000  # LLM._truncate would cut the reply's tail otherwise


def test_pipeline_rss_source_extracts_a_whole_feed_in_one_call() -> None:
    feed = SAMPLES / "feed_opportunities.xml"
    report = run_ingestion(sources=[Source(name="t", url=str(feed), kind="rss")],
                           settings=_settings())
    assert report.extractions.made == 1  # one call for the entire feed
    assert report.items_fetched >= 2
