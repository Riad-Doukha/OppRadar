# LLM access layer: Gemini Flash (free tier), local Ollama, or a deterministic
# FakeLLM for offline work. Adds disk caching, rate limiting and retry/backoff
# on top of every provider. Called by: ingestion/, documents/, matching/, chat/.
#
# Nothing else in the package may call an LLM API directly.

from __future__ import annotations

import hashlib
import json
import logging
import re
import statistics
import threading
import time
import types
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter

from oppradar_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


class LLMError(RuntimeError):
    """Expected LLM failure (bad key, rate limit exhausted, malformed reply)."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class QuotaExhausted(LLMError):
    """Daily/rate quota is gone (429): retrying now cannot help, so we never do."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


# --------------------------------------------------------------------------- #
# Stats (shown in 00_setup.ipynb and the eval notebook)
# --------------------------------------------------------------------------- #
class LLMStats(BaseModel):
    calls: int = 0  # successful provider calls
    cached: int = 0  # served from the disk cache
    errors: int = 0  # logical calls that ended in an exception
    failed_attempts: int = 0  # provider attempts that failed (retries included)
    latency_p50_ms: float = 0.0  # median over the successful calls (0 = none)


_stats = LLMStats()
_latencies: list[float] = []  # ms of the successful calls, for the median


def get_stats() -> LLMStats:
    """Return counters for calls / cache hits / errors since last reset."""
    stats = _stats.model_copy()
    stats.latency_p50_ms = statistics.median(_latencies) if _latencies else 0.0
    return stats


def reset_stats() -> None:
    """Zero the counters (useful between evaluation runs)."""
    _stats.calls = _stats.cached = _stats.errors = _stats.failed_attempts = 0
    _latencies.clear()


class CallTelemetry(BaseModel):
    """One real provider call: which model answered, how long, how many tokens."""

    model: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    ok: bool = True


# --------------------------------------------------------------------------- #
# Gemini error classification: 429 = quota (never retried), 5xx = transient
# --------------------------------------------------------------------------- #
_QUOTA_MARKERS = (
    "429",
    "quota",
    "resource_exhausted",
    "resource exhausted",
    "resourc exhaust",
    "rate limit",
    "ratelimit",
    "too many requests",
)
_TRANSIENT_MARKERS = (
    "500",
    "502",
    "503",
    "504",
    "unavailable",
    "overloaded",
    "timeout",
    "timed out",
    "internal server",
    "internalserver",
    "internal error",
    "connection reset",
    "connection refused",
    "try again",
)


def _classify_gemini_error(exc: Exception) -> LLMError:
    """Map one SDK failure to QuotaExhausted (never retried) or a retryable error.

    429 / RESOURCE_EXHAUSTED means the daily free-tier budget is gone: the item
    becomes "pending LLM" instead of burning more calls. 5xx / timeouts are
    transient, so tenacity backs off with jitter and retries them.
    """
    blob = f"{type(exc).__name__} {exc}".lower()
    if getattr(exc, "code", None) == 429 or any(marker in blob for marker in _QUOTA_MARKERS):
        return QuotaExhausted(f"gemini quota exhausted: {exc}")
    if getattr(exc, "code", None) in (500, 502, 503, 504) or any(
        marker in blob for marker in _TRANSIENT_MARKERS
    ):
        return LLMError(f"gemini transient failure: {exc}", retryable=True)
    return LLMError(f"gemini call failed: {exc}", retryable=False)


# --------------------------------------------------------------------------- #
# Disk cache + rate limiter
# --------------------------------------------------------------------------- #
class DiskCache:
    """Content-addressed JSON cache: one file per (provider, model, prompt)."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or get_settings().cache_dir / "llm"
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(provider: str, model: str, prompt: str, schema_name: str = "") -> str:
        blob = f"{provider}|{model}|{schema_name}|{prompt}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:40]

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, key: str, payload: dict[str, Any]) -> None:
        path = self.directory / f"{key}.json"
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:  # a full disk must not kill a batch
            logger.warning("could not write LLM cache entry %s: %s", key[:8], exc)


class RateLimiter:
    """Enforces a minimum delay between provider calls (free-tier politeness)."""

    def __init__(self, min_delay: float) -> None:
        self.min_delay = min_delay
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            pause = self.min_delay - (time.monotonic() - self._last_call)
            if pause > 0:
                time.sleep(pause)
            self._last_call = time.monotonic()


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class LLM(ABC):
    """Base class: caching, rate limiting, retry and telemetry for every provider."""

    name = "base"

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self.settings = settings
        models = {"gemini": settings.gemini_model, "ollama": settings.ollama_model, "fake": "fake"}
        self.model = models[self.name]
        # Tried once when the primary model keeps failing on transient errors.
        self.fallback_model = settings.gemini_fallback_model if self.name == "gemini" else ""
        self.cache = DiskCache(settings.cache_dir / "llm")
        self.limiter = RateLimiter(settings.llm_min_delay_seconds)
        self.max_retries = settings.llm_max_retries
        self.retry_base_wait = settings.llm_retry_base_wait
        self.max_input_chars = settings.llm_max_input_chars
        self.last_call: CallTelemetry | None = None  # most recent real call
        self._last_tokens: tuple[int, int] = (0, 0)  # refilled by the provider

    # -- public API ---------------------------------------------------------
    def structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        """Ask for a JSON answer validated into `schema` (cached on disk).

        Example:
            >>> opp = llm.structured("Extract: ...", Opportunity)
        """
        clean = self._truncate(prompt)
        key = self._key(clean, schema.__name__, system)
        self.last_call = None  # a cache hit is free: it makes no real call
        cached = self.cache.get(key)
        if cached is not None:
            _stats.cached += 1
            return schema.model_validate(cached["data"])

        try:
            data, _call = self._call_with_retry(clean, schema, system, key)
        except LLMError:
            _stats.errors += 1
            raise
        try:
            return schema.model_validate(data)
        except Exception as exc:
            _stats.errors += 1
            raise LLMError(f"{self.name} returned invalid {schema.__name__}: {exc}") from exc

    def is_cached(self, prompt: str, schema: type[T], system: str | None = None) -> bool:
        """True when `structured()` would be a free disk-cache hit.

        Lets callers check the cache BEFORE counting against a per-run
        budget, so cached answers never consume the free-tier quota.
        """
        return (
            self.cache.get(self._key(self._truncate(prompt), schema.__name__, system)) is not None
        )

    def cached_meta(
        self, prompt: str, schema: type[T], system: str | None = None
    ) -> dict[str, Any] | None:
        """Provider/model recorded with the cached answer (None when uncached).

        Records written before the provenance fields existed report "unknown".
        The model field names the model that ACTUALLY answered, which may be
        the fallback one. Lets notebooks prove which model produced a record.

        Example:
            >>> meta = llm.cached_meta("...", SomeSchema, system="...")
            >>> meta is None or {"provider", "model"} <= set(meta)
            True
        """
        record = self.cache.get(self._key(self._truncate(prompt), schema.__name__, system))
        if record is None:
            return None
        return {
            "provider": str(record.get("provider") or "unknown"),
            "model": str(record.get("model") or "unknown"),
        }

    def text(self, prompt: str, system: str | None = None) -> str:
        """Ask for a plain-text answer (cached on disk)."""
        clean = self._truncate(prompt)
        key = self._key(clean, "text", system)
        self.last_call = None
        cached = self.cache.get(key)
        if cached is not None:
            _stats.cached += 1
            return str(cached["text"])

        try:
            result, call = self._with_fallback(
                lambda model: self._complete_text(clean, system, model)
            )
        except LLMError:
            _stats.errors += 1
            raise
        _stats.calls += 1
        self.cache.put(key, {"text": result, "provider": self.name, "model": call.model})
        return result

    # -- internals ------------------------------------------------------------
    def _key(self, prompt: str, schema_name: str, system: str | None) -> str:
        """Cache key of one (provider, primary model, system, prompt) request."""
        return self.cache.key(self.name, self.model, f"{system or ''}\n{prompt}", schema_name)

    def _call_with_retry(
        self, prompt: str, schema: type[BaseModel], system: str | None, key: str
    ) -> tuple[dict[str, Any], CallTelemetry]:
        data, call = self._with_fallback(
            lambda model: self._complete_structured(prompt, schema, system, model)
        )
        _stats.calls += 1
        self.cache.put(
            key,
            {
                "schema": schema.__name__,
                "data": data,
                "provider": self.name,
                "model": call.model,  # the model that really answered
            },
        )
        return data, call

    def _with_fallback(self, call: Callable[[str], R]) -> tuple[R, CallTelemetry]:
        """One logical call: retried on the primary model, then the fallback once.

        Only transient failures fall back; quota errors and malformed replies
        propagate immediately (retrying them only burns the daily limit).
        """
        self.limiter.wait()
        try:
            return self._retrying()(self._attempt, call, self.model)
        except LLMError as exc:
            if not (exc.retryable and self.fallback_model):
                raise
            logger.warning(
                "%s: %s failed after %d attempt(s) (%s); one call to %s",
                self.name,
                self.model,
                self.max_retries,
                exc,
                self.fallback_model,
            )
            self.limiter.wait()
            return self._attempt(call, self.fallback_model)

    def _attempt(self, call: Callable[[str], R], model: str) -> tuple[R, CallTelemetry]:
        """One timed provider attempt; tenacity retries it on transient errors."""
        self._last_tokens = (0, 0)
        started = time.perf_counter()  # perf_counter, not monotonic: on Windows
        try:  # monotonic() ticks only ~15.6 ms, which would report 0 for a fast call
            result = call(model)
        except Exception:
            self._note(model, started, ok=False)
            raise
        return result, self._note(model, started, ok=True)

    def _note(self, model: str, started: float, ok: bool) -> CallTelemetry:
        """Record and log one attempt: latency, input/output tokens, model."""
        call = CallTelemetry(
            model=model,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=self._last_tokens[0],
            output_tokens=self._last_tokens[1],
            ok=ok,
        )
        self.last_call = call
        if not ok:
            _stats.failed_attempts += 1
            return call
        _latencies.append(call.latency_ms)
        logger.info(
            "%s answered with %s in %.0f ms (tokens in=%d out=%d)",
            self.name,
            model,
            call.latency_ms,
            call.input_tokens,
            call.output_tokens,
        )
        return call

    def _retrying(self) -> Retrying:
        """Exponential backoff plus jitter, so parallel runs never sync up."""
        return Retrying(
            wait=wait_exponential_jitter(
                initial=self.retry_base_wait, exp_base=2, max=60, jitter=self.retry_base_wait
            ),
            stop=stop_after_attempt(self.max_retries),
            retry=self._is_retryable,
            reraise=True,
        )

    @staticmethod
    def _is_retryable(state) -> bool:  # tenacity state
        outcome = state.outcome
        if outcome is None:
            return False
        exc = outcome.exception()
        return isinstance(exc, LLMError) and exc.retryable

    def _truncate(self, prompt: str) -> str:
        if len(prompt) <= self.max_input_chars:
            return prompt
        logger.info("truncated LLM input from %d to %d chars", len(prompt), self.max_input_chars)
        return prompt[: self.max_input_chars] + "\n[...truncated...]"

    @abstractmethod
    def _complete_structured(
        self, prompt: str, schema: type[BaseModel], system: str | None, model: str
    ) -> dict:
        """Provider call returning a plain dict matching `schema`."""

    @abstractmethod
    def _complete_text(self, prompt: str, system: str | None, model: str) -> str:
        """Provider call returning text."""


class GeminiProvider(LLM):
    """Google Gemini Flash through the official `google-genai` SDK (free tier)."""

    name = "gemini"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
        types_module: Any | None = None,
    ) -> None:
        super().__init__(settings)
        settings = settings or get_settings()
        self.thinking_budget = settings.gemini_thinking_budget
        self.max_output_tokens = settings.gemini_max_output_tokens
        if client is not None:  # tests inject a scripted client (no SDK, no key)
            self._client = client
            self._types = types_module
            return
        if not settings.gemini_key_value:
            raise LLMError("GEMINI_API_KEY is empty — set it in ai/.env or use LLM_PROVIDER=fake")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("google-genai is not installed: pip install google-genai") from exc
        self._client = genai.Client(api_key=settings.gemini_key_value)
        self._types = __import__("google.genai", fromlist=["types"]).types

    def _generate(
        self, prompt: str, schema: type[BaseModel] | None, system: str | None, model: str
    ):
        """One SDK call; a model rejecting `thinking_config` loses it and retries once."""
        config = self._config(schema, system)
        try:
            return self._sdk_call(config, model, prompt)
        except Exception as exc:
            if not self._drop_thinking_config(config, exc):
                raise _classify_gemini_error(exc) from exc
            logger.warning("%s rejected thinking_config; retrying without it", model)
        try:
            return self._sdk_call(config, model, prompt)
        except Exception as exc:
            raise _classify_gemini_error(exc) from exc

    def _sdk_call(self, config: dict[str, Any], model: str, prompt: str) -> Any:
        return self._client.models.generate_content(
            model=model, contents=prompt, config=self._types.GenerateContentConfig(**config)
        )

    def _config(self, schema: type[BaseModel] | None, system: str | None) -> dict[str, Any]:
        """No thinking plus a hard output cap: the answer is small, latency matters."""
        config: dict[str, Any] = {
            "temperature": 0.2,
            "max_output_tokens": self.max_output_tokens,
        }
        thinking = self._thinking_config()
        if thinking is not None:
            config["thinking_config"] = thinking
        if system:
            config["system_instruction"] = system
        if schema is not None:
            config["response_schema"] = schema
            config["response_mime_type"] = "application/json"
        return config

    def _thinking_config(self) -> Any | None:
        """Smallest thinking level the SDK supports (0 = no thinking at all)."""
        if self.thinking_budget < 0:
            return None
        cls = getattr(self._types, "ThinkingConfig", None)
        return None if cls is None else cls(thinking_budget=self.thinking_budget)

    def _drop_thinking_config(self, config: dict[str, Any], exc: Exception) -> bool:
        """Self-heal: some model families reject `thinking_config` with a 400."""
        if "thinking_config" not in config or getattr(exc, "code", None) != 400:
            return False
        if "thinking" not in f"{type(exc).__name__} {exc}".lower():
            return False
        config.pop("thinking_config", None)
        self.thinking_budget = -1  # never send it again in this process
        return True

    def _complete_structured(self, prompt, schema, system, model) -> dict:
        response = self._generate(prompt, schema, system, model)
        self._last_tokens = _usage_of(response)
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return parsed.model_dump(mode="json") if isinstance(parsed, BaseModel) else dict(parsed)
        text = (response.text or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"gemini returned non-JSON: {text[:120]}", retryable=True) from exc

    def _complete_text(self, prompt, system, model) -> str:
        response = self._generate(prompt, None, system, model)
        self._last_tokens = _usage_of(response)
        if not response.text:
            raise LLMError("gemini returned an empty response", retryable=True)
        return response.text


def _usage_of(response: Any) -> tuple[int, int]:
    """(input, output) token counts reported by Gemini (0 when unavailable)."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0, 0
    return (
        int(getattr(usage, "prompt_token_count", 0) or 0),
        int(getattr(usage, "candidates_token_count", 0) or 0),
    )


class OllamaProvider(LLM):
    """Local Ollama server (http://localhost:11434) — free, no key required."""

    name = "ollama"

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings)
        self.base_url = self.settings.ollama_base_url.rstrip("/")

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"ollama unreachable at {self.base_url}: {exc}", retryable=True) from exc

    def _complete_structured(self, prompt, schema, system, model) -> dict:
        payload = {
            "model": model,
            "messages": self._messages(prompt, system),
            "format": schema.model_json_schema(),
            "stream": False,
        }
        reply = self._post(payload)
        self._last_tokens = _eval_counts(reply)
        content = reply.get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"ollama returned non-JSON: {content[:120]}", retryable=True) from exc

    def _complete_text(self, prompt, system, model) -> str:
        payload = {"model": model, "messages": self._messages(prompt, system), "stream": False}
        reply = self._post(payload)
        self._last_tokens = _eval_counts(reply)
        return reply.get("message", {}).get("content", "")

    @staticmethod
    def _messages(prompt: str, system: str | None) -> list[dict[str, str]]:
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        return messages


def _eval_counts(reply: dict[str, Any]) -> tuple[int, int]:
    """(prompt, output) token counts reported by Ollama (0 when unavailable)."""
    return int(reply.get("prompt_eval_count") or 0), int(reply.get("eval_count") or 0)


class FakeLLM(LLM):
    """Deterministic offline provider: schema-valid canned data, zero network.

    Lets every test and notebook run with LLM_PROVIDER=fake. Answers are stable
    for a given prompt, so caching and determinism tests are meaningful.
    """

    name = "fake"

    def _complete_structured(self, prompt, schema, system, model) -> dict:
        return _canned(schema, prompt)

    def _complete_text(self, prompt, system, model) -> str:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:6]
        return f"[fake answer {digest}] Based on the provided sources, here is a short reply."


# --------------------------------------------------------------------------- #
# Canned data for FakeLLM
# --------------------------------------------------------------------------- #
_CANNED: dict[str, dict[str, Any]] = {
    "Opportunity": {
        "title": "Fake Scholarship for Testing",
        "organizer": "OppRadar Fake Foundation",
        "type": "scholarship",
        "mode": "remote",
        "location": "Online",
        "country": "Algeria",
        "deadline": None,
        "funding": "Full funding",
        "eligibility": ["Open to students"],
        "benefits": ["Tuition covered"],
        "summary": "A synthetic opportunity returned by the fake LLM provider.",
        "url": "https://example.org/fake-scholarship",
        "source": "fake-llm",
        "trust_level": "unknown",
        "added_via": "pipeline",
    },
    "Profile": {
        "full_name": "Fake User",
        "headline": "Testing profile",
        "skills": ["python", "testing"],
        "languages": ["english"],
        "summary": "Synthetic profile produced by the fake LLM provider.",
        "preferences": {},
    },
    "ChatAnswer": {
        "answer": "[fake] I can only answer from the sources you provide; this is canned text.",
        "language": "en",
        "citations": [],
        "in_source": False,
    },
    "EligibilityAssessment": {
        "eligible": None,
        "met": [],
        "gaps": ["No profile information available to compare."],
        "next_steps": ["Upload a CV to assess eligibility."],
    },
    # matching/ (Phase 4) — the fake model rewords whatever rules it is given
    "PhrasedReasons": {
        "reasons": [
            "[fake] The rules confirmed this matches your background.",
            "[fake] It also fits what you said you are looking for.",
            "[fake] The deadline in the source is still open.",
        ],
    },
    # documents/ (Phase 2) — empty e-mail/links so the regex backfill is exercised
    "CVExtraction": {
        "full_name": "Fake Person",
        "headline": "Test Candidate",
        "email": "",
        "phone": "",
        "country": "Algeria",
        "summary": "Deterministic fake CV produced by the offline provider.",
        "skills": ["python", "pytest"],
        "languages": ["french", "english"],
        "interests": ["ai"],
        "education": [
            {
                "institution": "Fake University",
                "degree": "MSc",
                "field": "Data Science",
                "start_date": "2022",
                "end_date": "2024",
            }
        ],
        "experience": [
            {
                "organization": "Fake Corp",
                "title": "Intern",
                "start_date": "2023",
                "end_date": "2023",
                "description": "Built tests.",
            }
        ],
        "certificates": [],
        "projects": [
            {
                "name": "Fake Project",
                "description": "",
                "url": "https://example.org/fake",
                "technologies": ["python"],
            }
        ],
        "links": [],
        "needs_review": ["headline"],
    },
    "CertificateExtraction": {
        "title": "Fake Certificate",
        "issuer": "Fake Issuer",
        "holder": "Fake Person",
        "issued_on": "2024",
        "hours": 10,
        "credential_url": "",
        "skills": ["python"],
        "needs_review": ["issued_on"],
    },
    "PortfolioExtraction": {
        "full_name": "Fake Person",
        "email": "",
        "links": [],
        "projects": [
            {
                "name": "Fake Portfolio Project",
                "description": "",
                "url": "https://example.org/p",
                "technologies": ["python"],
            }
        ],
        "needs_review": [],
    },
    # ingestion/ (Phase 3) — deadline exactly as written (never invented);
    # the converter normalizes it to ISO. `location` is low-confidence on
    # purpose so the "to verify" path is exercised offline too.
    "OpportunityExtraction": {
        "title": "Atlas Merit Scholarship 2027",
        "organizer": "Atlas Digital Foundation",
        "type": "scholarship",
        "mode": "remote",
        "location": "Online",
        "country": "Algeria",
        "funding": "Full funding",
        "eligibility": ["Open to students", "Under 30 years old"],
        "benefits": ["Tuition covered", "Mentorship"],
        "summary": "A synthetic scholarship returned by the fake LLM provider.",
        "deadline": "March 15, 2027",
        "is_opportunity": True,
        "not_opportunity_reason": None,
        "field_confidences": [
            {"field": "title", "confidence": 0.95},
            {"field": "organizer", "confidence": 0.9},
            {"field": "deadline", "confidence": 0.9},
            {"field": "location", "confidence": 0.5},
        ],
    },
}


_LISTICLE_RE = re.compile(r"\btop\s+\d+\b", re.IGNORECASE)
_ITEM_BLOCK_RE = re.compile(r"===\s*ITEM\s+\d+\s*===\s*\n?")

# Batch templates: 0/1 cycle for real entries, 2 is the listicle used for
# "Top 10 ..." blocks — so the offline provider exercises acceptance and
# rejection inside one batch.
_BATCH_TEMPLATES: list[dict[str, Any]] = [
    {
        "title": "Atlas Merit Scholarship 2027",
        "organizer": "Atlas Digital Foundation",
        "type": "scholarship",
        "mode": "remote",
        "location": "Online",
        "country": "Algeria",
        "funding": "Full funding",
        "eligibility": ["Open to students", "Under 30 years old"],
        "benefits": ["Tuition covered", "Mentorship"],
        "summary": "A synthetic scholarship returned by the fake LLM provider.",
        "deadline": "March 15, 2027",
        "is_opportunity": True,
        "field_confidences": [
            {"field": "title", "confidence": 0.95},
            {"field": "deadline", "confidence": 0.9},
        ],
    },
    {
        "title": "Cedar Hackathon 2027",
        "organizer": "Cedar Labs",
        "type": "hackathon",
        "mode": "hybrid",
        "location": "Algiers",
        "country": "Algeria",
        "funding": None,
        "eligibility": ["Students only"],
        "benefits": ["Mentorship", "Prizes"],
        "summary": "A synthetic hackathon returned by the fake LLM provider.",
        "deadline": "",
        "is_opportunity": True,
        "field_confidences": [
            {"field": "title", "confidence": 0.9},
            {"field": "deadline", "confidence": 0.2},
        ],
    },
    {
        "title": "Top 10 Scholarships of 2026",
        "organizer": "",
        "summary": "A ranked listicle returned by the fake LLM provider.",
        "deadline": "",
        "is_opportunity": False,
        "not_opportunity_reason": "listicle (fake-provider rule)",
        "field_confidences": [{"field": "title", "confidence": 0.9}],
    },
]


def _canned(schema: type[BaseModel], prompt: str) -> dict[str, Any]:
    """Build a deterministic, schema-valid dict for any Pydantic schema."""
    canned = _CANNED.get(schema.__name__)
    if canned is not None:
        data = dict(canned)
        # Keep fake output valid even if the schema changes fields later.
        data = {k: v for k, v in data.items() if k in schema.model_fields}
    else:
        data = {}
    if schema.__name__ == "OpportunityExtraction" and _LISTICLE_RE.search(prompt[:300]):
        # Deterministic fake rule: "Top 10 ..." headlines are listicles, so
        # the offline provider exercises the is_opportunity rejection path.
        data["is_opportunity"] = False
        data["not_opportunity_reason"] = "listicle (fake-provider rule)"
    if schema.__name__ == "OpportunityBatchExtraction":
        data["items"] = _canned_batch_items(prompt)
    for name, field in schema.model_fields.items():
        if name not in data:
            data[name] = _default_for(field.annotation, name, depth=0)
    logger.debug(
        "fake LLM produced %s (prompt hash %s)",
        schema.__name__,
        hashlib.sha1(prompt.encode()).hexdigest()[:8],
    )
    return data


def _canned_batch_items(prompt: str) -> list[dict[str, Any]]:
    """One canned item per "=== ITEM n ===" block, cycled from the templates.

    A block whose text matches the single-item listicle rule ("Top 10 ...")
    becomes is_opportunity=false, so the offline pipeline exercises acceptance
    and rejection inside one batch. Titles carry their 1-based item number so
    every extracted record gets a distinct deterministic id.

    Example:
        >>> items = _canned_batch_items("=== ITEM 1 ===\\nTop 10 scholarships")
        >>> len(items), items[0]["is_opportunity"], items[0]["title"]
        (1, False, 'Top 10 Scholarships of 2026 #1')
    """
    blocks = [b.strip() for b in _ITEM_BLOCK_RE.split(prompt) if b.strip()]
    return [_canned_batch_item(i, block) for i, block in enumerate(blocks)]


def _canned_batch_item(index: int, block: str) -> dict[str, Any]:
    is_listicle = bool(_LISTICLE_RE.search(block[:300]))
    item = dict(_BATCH_TEMPLATES[2] if is_listicle else _BATCH_TEMPLATES[index % 2])
    item["title"] = f"{item['title']} #{index + 1}"
    if is_listicle:
        item["is_opportunity"] = False
        item["not_opportunity_reason"] = "listicle (fake-provider rule)"
    return item


def _default_for(annotation, name: str, depth: int) -> Any:
    """Fill any annotation with a plausible, valid default value."""
    from enum import Enum
    from typing import Literal, Union, get_args, get_origin

    if depth > 4:
        return None
    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is bool:
        return False
    if annotation is int:
        return 0
    if annotation is float:
        return 0.5
    if annotation is str or annotation is Path:
        return f"fake {name.replace('_', ' ')}"
    if origin is Literal:
        return args[0]
    if origin in (list, tuple, set):
        inner = args[0] if args else str
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return [_default_for(inner, name, depth + 1)]
        return []
    if origin in (Union, types.UnionType):
        for arg in args:
            if arg is type(None):
                continue
            return _default_for(arg, name, depth + 1)
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {
            f: _default_for(field.annotation, f, depth + 1)
            for f, field in annotation.model_fields.items()
        }
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return next(iter(annotation)).value
    return None


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def get_llm(provider: str | None = None) -> LLM:
    """Return the configured provider (gemini | ollama | fake), built once.

    Example:
        >>> llm = get_llm()          # honours LLM_PROVIDER in .env
        >>> llm = get_llm("fake")    # force the offline provider
    """
    provider = provider or get_settings().llm_provider
    key = f"llm-{provider}"
    instance = _INSTANCES.get(key)
    if instance is None:
        classes = {"gemini": GeminiProvider, "ollama": OllamaProvider, "fake": FakeLLM}
        if provider not in classes:
            raise LLMError(f"unknown LLM provider {provider!r}; choose from {sorted(classes)}")
        instance = classes[provider]()
        _INSTANCES[key] = instance
    return instance


_INSTANCES: dict[str, LLM] = {}
