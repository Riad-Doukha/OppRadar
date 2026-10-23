# Gemini reliability (Phase 3e): transient 503s are retried with jittered
# backoff, the fallback model is tried exactly once, quota errors (429) are
# never retried, "made" counts only successes, and an item no model could
# answer stays "pending LLM" — never cached, never stored. Fully offline:
# a scripted client stands in for the google-genai SDK.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel
from tenacity import wait_exponential_jitter

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.extract import extract_record
from oppradar_ai.ingestion.pipeline import run_ingestion
from oppradar_ai.llm import (
    GeminiProvider,
    LLMError,
    QuotaExhausted,
    _canned,
    get_stats,
    reset_stats,
)
from oppradar_ai.schemas import OpportunityExtraction, Source

PRIMARY = "gemini-3.8-flash"
FALLBACK = "gemini-3.5-flash"
SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


@pytest.fixture(autouse=True)
def _fresh_stats():
    """Every test starts from zero LLM counters (they are process-global)."""
    reset_stats()


class _Answer(BaseModel):
    """Smallest possible schema: keeps the provider tests independent of ingestion."""

    title: str
    deadline: str | None = None


class _StubTypes:
    """Stand-in for google.genai.types: configs are recorded, not validated."""

    class GenerateContentConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class ThinkingConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs


class _Response:
    def __init__(self, payload: str, *, input_tokens: int = 812, output_tokens: int = 190) -> None:
        self.text = payload
        self.parsed = None
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=input_tokens, candidates_token_count=output_tokens
        )


class _ScriptedClient:
    """Fake `genai.Client`: fails a scripted number of times, then answers.

    `failures` maps a model to how often it errors before answering;
    `always_fail` maps a model to the error it raises on every call;
    `fail_on_config` maps a config key to the error raised while that key is
    still present (used by the thinking_config self-healing test).
    """

    def __init__(
        self,
        *,
        failures: dict[str, int] | None = None,
        always_fail: dict[str, Exception] | None = None,
        fail_on_config: dict[str, Exception] | None = None,
        payload: str | None = None,
    ) -> None:
        self.failures = dict(failures or {})
        self.always_fail = dict(always_fail or {})
        self.fail_on_config = dict(fail_on_config or {})
        self.calls: list[str] = []
        self.configs: list[Any] = []
        self._payload = payload or json.dumps({"title": "Scripted Answer 2027"})

    @property
    def models(self) -> _ScriptedClient:
        return self

    def generate_content(self, *, model: str, contents: str, config: Any = None) -> _Response:
        self.calls.append(model)
        self.configs.append(config)
        if model in self.always_fail:
            raise self.always_fail[model]
        for key, error in self.fail_on_config.items():
            if key in getattr(config, "kwargs", {}):
                raise error
        if self.failures.get(model, 0) > 0:
            self.failures[model] -= 1
            raise _api_error(503)
        return _Response(self._payload)


def _api_error(code: int, message: str = "backend unavailable") -> Exception:
    """An exception shaped like google.genai.errors.APIError (it has `.code`)."""
    exc = RuntimeError(f"{code} None. {{'error': {{'message': {message!r}}}}}")
    exc.code = code  # type: ignore[attr-defined]
    return exc


def _settings(tmp_path: Path, **overrides: Any):
    base = dict(
        data_dir=tmp_path,
        fetch_delay_seconds=0.0,
        llm_min_delay_seconds=0.0,
        llm_max_retries=3,
        llm_retry_base_wait=0.01,
        gemini_model=PRIMARY,
        gemini_fallback_model=FALLBACK,
        gemini_thinking_budget=0,
        gemini_max_output_tokens=512,
    )
    base.update(overrides)
    return get_settings().model_copy(update=base)


def _provider(settings: Any, client: _ScriptedClient) -> GeminiProvider:
    return GeminiProvider(settings, client=client, types_module=_StubTypes)


def _extraction_payload() -> str:
    """Canned, schema-valid OpportunityExtraction JSON (FakeLLM's own source)."""
    return json.dumps(_canned(OpportunityExtraction, "scripted text"))


# --------------------------------------------------------------------------- #
# Retries, fallback model, quota
# --------------------------------------------------------------------------- #
def test_transient_503_is_retried_until_the_primary_answers(tmp_path: Path) -> None:
    client = _ScriptedClient(failures={PRIMARY: 2})
    provider = _provider(_settings(tmp_path), client)

    answer = provider.structured("scripted prompt alpha", _Answer)

    assert answer.title == "Scripted Answer 2027"
    assert client.calls == [PRIMARY, PRIMARY, PRIMARY]  # 2 failures, then success
    assert provider.last_call is not None and provider.last_call.ok
    assert provider.last_call.model == PRIMARY
    assert provider.last_call.latency_ms >= 0.0
    assert (provider.last_call.input_tokens, provider.last_call.output_tokens) == (812, 190)
    stats = get_stats()
    assert (stats.calls, stats.errors, stats.failed_attempts) == (1, 0, 2)


def test_gives_up_after_max_retries_when_there_is_no_fallback(tmp_path: Path) -> None:
    client = _ScriptedClient(always_fail={PRIMARY: _api_error(503)})
    provider = _provider(_settings(tmp_path, gemini_fallback_model=""), client)

    with pytest.raises(LLMError) as excinfo:
        provider.structured("scripted prompt beta", _Answer)

    assert excinfo.value.retryable  # transient, so it WAS retried
    assert client.calls == [PRIMARY] * 3  # llm_max_retries attempts, not one more
    assert provider.last_call is not None and not provider.last_call.ok
    assert get_stats().errors == 1


def test_fallback_model_answers_once_the_primary_gives_up(tmp_path: Path) -> None:
    client = _ScriptedClient(always_fail={PRIMARY: _api_error(503)})
    provider = _provider(_settings(tmp_path), client)

    answer = provider.structured("scripted prompt gamma", _Answer)

    assert answer.title == "Scripted Answer 2027"
    assert client.calls == [PRIMARY] * 3 + [FALLBACK]  # retries, then ONE fallback call
    assert provider.cached_meta("scripted prompt gamma", _Answer) == {
        "provider": "gemini",
        "model": FALLBACK,  # the model that really answered is recorded
    }
    assert (get_stats().calls, get_stats().failed_attempts) == (1, 3)


def test_fallback_answer_is_cached_free_for_the_next_run(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    broken = _ScriptedClient(always_fail={PRIMARY: _api_error(503)})
    _provider(settings, broken).structured("scripted prompt delta", _Answer)

    healthy = _ScriptedClient()
    rerun = _provider(settings, healthy)

    assert rerun.structured("scripted prompt delta", _Answer).title == "Scripted Answer 2027"
    assert healthy.calls == []  # the cached answer cost nothing
    assert rerun.cached_meta("scripted prompt delta", _Answer)["model"] == FALLBACK
    assert broken.calls.count(FALLBACK) == 1  # the fallback was used exactly once


def test_quota_error_is_never_retried_nor_fallen_back(tmp_path: Path) -> None:
    client = _ScriptedClient(always_fail={PRIMARY: _api_error(429, "quota exceeded")})
    provider = _provider(_settings(tmp_path), client)

    with pytest.raises(QuotaExhausted):
        provider.structured("scripted prompt epsilon", _Answer)

    assert client.calls == [PRIMARY]  # exactly one attempt: no retry, no fallback
    assert get_stats().failed_attempts == 1


def test_retries_use_exponential_backoff_with_jitter(tmp_path: Path) -> None:
    provider = _provider(_settings(tmp_path), _ScriptedClient())
    assert isinstance(provider._retrying().wait, wait_exponential_jitter)


# --------------------------------------------------------------------------- #
# Latency controls
# --------------------------------------------------------------------------- #
def test_no_thinking_and_a_hard_output_cap_are_requested(tmp_path: Path) -> None:
    client = _ScriptedClient()
    _provider(_settings(tmp_path, gemini_max_output_tokens=512), client).structured("hi", _Answer)

    config = client.configs[0].kwargs
    assert config["thinking_config"].kwargs == {"thinking_budget": 0}
    assert config["max_output_tokens"] == 512


def test_model_rejecting_the_thinking_config_is_healed_once(tmp_path: Path) -> None:
    client = _ScriptedClient(
        fail_on_config={"thinking_config": _api_error(400, "invalid thinking_config")}
    )
    provider = _provider(_settings(tmp_path), client)

    answer = provider.structured("scripted prompt zeta", _Answer)

    assert answer.title == "Scripted Answer 2027"
    assert client.calls == [PRIMARY, PRIMARY]  # the second try dropped the config
    assert "thinking_config" not in client.configs[1].kwargs
    assert provider.thinking_budget == -1  # and never sent again in this process


# --------------------------------------------------------------------------- #
# Ingestion: pending items, budget accounting, nothing junk is kept
# --------------------------------------------------------------------------- #
def test_pending_item_when_quota_is_gone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    client = _ScriptedClient(always_fail={PRIMARY: _api_error(429, "quota exceeded")})
    monkeypatch.setattr(
        "oppradar_ai.ingestion.extract.get_llm", lambda: _provider(settings, client)
    )
    budget = RunBudget(settings, max_extractions=5)

    first = extract_record(
        "quota unique text 15 March 2027 qa7",
        url="https://example.org/q1",
        source_name="unit",
        budget=budget,
        settings=settings,
    )
    second = extract_record(
        "quota unique text 16 March 2027 qa8",
        url="https://example.org/q2",
        source_name="unit",
        budget=budget,
        settings=settings,
    )

    assert first.opportunity is None and first.pending is not None
    assert "quota exhausted" in first.pending.reason
    assert budget.extractions.made == 0
    assert budget.extractions.failed_attempts == 1  # a 429 still spent a slot
    assert second.pending is not None and "quota exhausted" in second.pending.reason
    assert budget.extractions.skipped == 1  # short-circuited, no second call
    assert client.calls == [PRIMARY]  # the quota error stopped the run early


def test_retries_are_invisible_to_the_budget_but_not_to_the_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One logical call = one slot; its internal retries stay visible in stats."""
    settings = _settings(tmp_path)
    client = _ScriptedClient(failures={PRIMARY: 2}, payload=_extraction_payload())
    monkeypatch.setattr(
        "oppradar_ai.ingestion.extract.get_llm", lambda: _provider(settings, client)
    )
    budget = RunBudget(settings, max_extractions=1)

    out = extract_record(
        "flaky unique text 17 March 2027 qa9",
        url="https://example.org/f1",
        source_name="unit",
        budget=budget,
        settings=settings,
    )

    assert out.opportunity is not None  # the retried call finally answered
    assert budget.extractions.made == 1
    assert budget.extractions.failed_attempts == 0  # a retry is not a lost item
    assert get_stats().failed_attempts == 2  # ...but the two 503s are counted
    assert budget.latency_p50_ms() > 0.0  # one real answer -> a real latency
    assert out.llm_latency_ms > 0.0


def test_items_no_model_could_answer_are_never_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, gemini_fallback_model="")
    client = _ScriptedClient(always_fail={PRIMARY: _api_error(503)}, payload=_extraction_payload())
    monkeypatch.setattr(
        "oppradar_ai.ingestion.extract.get_llm", lambda: _provider(settings, client)
    )

    report = run_ingestion(
        sources=[
            Source(
                name="sample-scholarship",
                url=str(SAMPLES / "page_scholarship.html"),
                kind="page",
            )
        ],
        settings=settings,
    )

    assert report.opportunities == []  # nothing was stored
    assert report.items_new == 0
    assert report.pending_llm, "the page must wait for a working LLM"
    assert report.pending_llm[0].title and report.pending_llm[0].url
    assert "llm failed" in report.pending_llm[0].reason
    assert report.extractions.made == 0
    assert report.extractions.failed_attempts >= 1
    assert report.extraction_p50_latency_ms == 0.0
    assert not list((settings.cache_dir / "llm").glob("*.json"))  # never cached


def test_run_report_carries_median_latency_and_retry_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    client = _ScriptedClient(failures={PRIMARY: 1}, payload=_extraction_payload())
    monkeypatch.setattr(
        "oppradar_ai.ingestion.extract.get_llm", lambda: _provider(settings, client)
    )

    report = run_ingestion(
        sources=[
            Source(
                name="sample-scholarship",
                url=str(SAMPLES / "page_scholarship.html"),
                kind="page",
            )
        ],
        settings=settings,
    )

    assert report.items_new == 1
    assert report.extractions.made == 1  # the retried call succeeded...
    assert report.extractions.failed_attempts == 0  # ...so no item was lost
    assert get_stats().failed_attempts == 1  # the 503 is still counted
    assert report.extraction_p50_latency_ms > 0.0  # and the run reports latency
    assert report.pending_llm == []
