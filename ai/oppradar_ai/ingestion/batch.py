# Free-tier batching: several feed entries -> ONE Gemini call. The entries
# are numbered into a single prompt, the reply is matched back by index, and
# every per-item rule of extract.py applies unchanged (is_opportunity gate,
# rule-first deadlines, pending-never-fake). Called by: ingestion/pipeline.py.

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.extract import (
    RawExtraction,
    budgeted_structured,
    llm_identity,
    outcome_from_extraction,
    truncate_text,
)
from oppradar_ai.llm import get_llm
from oppradar_ai.schemas import (
    OpportunityBatchExtraction,
    OpportunityExtraction,
    OpportunityType,
)

logger = logging.getLogger(__name__)

# Prompt-marker overhead the per-entry char budget gives back to the entries.
_PROMPT_OVERHEAD_CHARS = 500

# How much of an entry reaches the model inside a batch. With the default
# llm_max_input_chars=8000 and batch size 5, each entry keeps 1500 chars —
# enough for a feed summary with its "Deadline:" line near the top.
_MIN_ENTRY_CHARS = 300


class BatchInput(BaseModel):
    """One entry to extract inside a batch call (mirrors extract_record's inputs)."""

    text: str
    url: str = ""
    source_name: str = "unknown"
    title_hint: str = ""
    type_hint: OpportunityType = OpportunityType.OTHER
    language: str = "en"
    country: str = ""


def extract_records_batch(
    inputs: list[BatchInput],
    *,
    budget: RunBudget | None = None,
    settings: Settings | None = None,
    checked_at: datetime | None = None,
) -> list[RawExtraction]:
    """Extract every input with one LLM call per `settings.extraction_batch_size` items.

    One call covers a whole chunk, so a run's `max_extractions_per_run` budget
    buys `batch_size` times more items than before. Guarantees per item are the
    same as `extract_record`'s; one failing chunk never affects the others and
    a failing call makes its whole chunk `pending` (never fabricated).

    Example:
        >>> outs = extract_records_batch([BatchInput(text="Deadline: 1 April 2027.")])
        >>> len(outs), outs[0].opportunity is not None or outs[0].pending is not None
        (1, True)
    """
    settings = settings or get_settings()
    budget = budget or RunBudget(settings)
    checked = checked_at or datetime.now(timezone.utc)
    size = max(1, settings.extraction_batch_size)
    outcomes: list[RawExtraction] = []
    for start in range(0, len(inputs), size):
        chunk = inputs[start : start + size]
        outcomes.extend(_chunk_outcomes(chunk, budget, settings, checked))
    return outcomes


def chunk_prompt(chunk: list[BatchInput], settings: Settings | None = None) -> str:
    """Numbered "=== ITEM n ===" blocks; each entry capped so the prompt fits.

    Example:
        >>> print(chunk_prompt([BatchInput(text="a"), BatchInput(text="b")]))
        === ITEM 1 ===
        a
        <BLANKLINE>
        === ITEM 2 ===
        b
    """
    settings = settings or get_settings()
    budget_chars = max(
        _MIN_ENTRY_CHARS,
        (settings.llm_max_input_chars - _PROMPT_OVERHEAD_CHARS) // max(1, len(chunk)),
    )
    return "\n\n".join(
        f"=== ITEM {i + 1} ===\n{truncate_text(item.text, budget_chars)}"
        for i, item in enumerate(chunk)
    )


def _chunk_outcomes(
    chunk: list[BatchInput], budget: RunBudget, settings: Settings, checked: datetime
) -> list[RawExtraction]:
    """One LLM call for one chunk; every entry pending when no model answered."""
    system = (settings.prompts_dir / "extract_batch.md").read_text(encoding="utf-8")
    prompt = chunk_prompt(chunk, settings)
    llm = get_llm()
    batch, failure = budgeted_structured(
        llm, prompt, system, budget, OpportunityBatchExtraction
    )
    provider, model = llm_identity(llm, prompt, system, OpportunityBatchExtraction)
    latency = llm.last_call.latency_ms if (llm.last_call and llm.last_call.ok) else 0.0
    if batch is None:
        return [
            _pending(item, failure or "no LLM answer", settings, checked, provider, model)
            for item in chunk
        ]
    if len(batch.items) > len(chunk):
        logger.warning(
            "batch reply had %d extra items; dropped", len(batch.items) - len(chunk)
        )
    return _answered_outcomes(
        chunk, batch.items, failure, settings, checked, provider, model, latency
    )


def _answered_outcomes(
    chunk: list[BatchInput],
    items: list[OpportunityExtraction],
    failure: str,
    settings: Settings,
    checked: datetime,
    provider: str,
    model: str,
    latency: float,
) -> list[RawExtraction]:
    """Match the reply to the entries by index; uncovered entries go pending."""
    outcomes = [
        outcome_from_extraction(
            extraction,
            text=item.text,
            url=item.url,
            source_name=item.source_name,
            title_hint=item.title_hint,
            type_hint=item.type_hint,
            language=item.language,
            country=item.country,
            settings=settings,
            checked_at=checked,
            provider=provider,
            model=model,
            latency_ms=latency,
        )
        for item, extraction in zip(chunk, items, strict=False)
    ]
    for item in chunk[len(items) :]:  # a short reply never fabricates the tail
        outcomes.append(
            _pending(
                item,
                f"batch reply covered {len(items)} of {len(chunk)} entries",
                settings,
                checked,
                provider,
                model,
            )
        )
    return outcomes


def _pending(
    item: BatchInput,
    failure: str,
    settings: Settings,
    checked: datetime,
    provider: str,
    model: str,
) -> RawExtraction:
    """One uncovered entry: a pending row, retried by the next run."""
    return outcome_from_extraction(
        None,
        text=item.text,
        url=item.url,
        source_name=item.source_name,
        title_hint=item.title_hint,
        settings=settings,
        checked_at=checked,
        failure=failure,
        provider=provider,
        model=model,
    )