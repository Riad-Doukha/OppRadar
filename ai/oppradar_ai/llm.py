# LLM access layer: Gemini Flash (free tier), local Ollama, or a deterministic
# FakeLLM for offline work. Adds disk caching, rate limiting and retry/backoff
# on top of every provider. Called by: ingestion/, documents/, matching/, chat/.
#
# Nothing else in the package may call an LLM API directly.

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import types
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from tenacity import Retrying, stop_after_attempt, wait_exponential

from oppradar_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Expected LLM failure (bad key, rate limit exhausted, malformed reply)."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


# --------------------------------------------------------------------------- #
# Stats (shown in 00_setup.ipynb and the eval notebook)
# --------------------------------------------------------------------------- #
class LLMStats(BaseModel):
    calls: int = 0  # actual provider invocations
    cached: int = 0  # served from the disk cache
    errors: int = 0


_stats = LLMStats()


def get_stats() -> LLMStats:
    """Return counters for calls / cache hits / errors since last reset."""
    return _stats.model_copy()


def reset_stats() -> None:
    """Zero the counters (useful between evaluation runs)."""
    _stats.calls = _stats.cached = _stats.errors = 0


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
    """Base class: caching, rate limiting and retry wrap every provider."""

    name = "base"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.gemini_model if self.name == "gemini" else settings.ollama_model
        if self.name == "fake":
            self.model = "fake"
        self.cache = DiskCache()
        self.limiter = RateLimiter(settings.llm_min_delay_seconds)
        self.max_retries = settings.llm_max_retries
        self.retry_base_wait = settings.llm_retry_base_wait
        self.max_input_chars = settings.llm_max_input_chars

    # -- public API ---------------------------------------------------------
    def structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        """Ask for a JSON answer validated into `schema` (cached on disk).

        Example:
            >>> opp = llm.structured("Extract: ...", Opportunity)
        """
        clean = self._truncate(prompt)
        key = self.cache.key(self.name, self.model, f"{system or ''}\n{clean}", schema.__name__)
        cached = self.cache.get(key)
        if cached is not None:
            _stats.cached += 1
            return schema.model_validate(cached["data"])

        data = self._call_with_retry(clean, schema, system, key)
        try:
            return schema.model_validate(data)
        except Exception as exc:
            _stats.errors += 1
            raise LLMError(f"{self.name} returned invalid {schema.__name__}: {exc}") from exc

    def text(self, prompt: str, system: str | None = None) -> str:
        """Ask for a plain-text answer (cached on disk)."""
        clean = self._truncate(prompt)
        key = self.cache.key(self.name, self.model, f"{system or ''}\n{clean}", "text")
        cached = self.cache.get(key)
        if cached is not None:
            _stats.cached += 1
            return str(cached["text"])

        self.limiter.wait()
        try:
            result = self._retrying()(self._complete_text, clean, system)
        except LLMError:
            _stats.errors += 1
            raise
        _stats.calls += 1
        self.cache.put(key, {"text": result})
        return result

    # -- internals ------------------------------------------------------------
    def _call_with_retry(
        self, prompt: str, schema: type[BaseModel], system: str | None, key: str
    ) -> dict[str, Any]:
        self.limiter.wait()
        try:
            result = self._retrying()(self._complete_structured, prompt, schema, system)
        except LLMError:
            _stats.errors += 1
            raise
        _stats.calls += 1
        self.cache.put(key, {"schema": schema.__name__, "data": result})
        return result

    def _retrying(self) -> Retrying:
        return Retrying(
            wait=wait_exponential(multiplier=self.retry_base_wait, max=60),
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
        self, prompt: str, schema: type[BaseModel], system: str | None
    ) -> dict:
        """Provider call returning a plain dict matching `schema`."""

    @abstractmethod
    def _complete_text(self, prompt: str, system: str | None) -> str:
        """Provider call returning text."""


class GeminiProvider(LLM):
    """Google Gemini Flash through the official `google-genai` SDK (free tier)."""

    name = "gemini"

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        settings = settings or get_settings()
        if not settings.gemini_key_value:
            raise LLMError("GEMINI_API_KEY is empty — set it in ai/.env or use LLM_PROVIDER=fake")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("google-genai is not installed: pip install google-genai") from exc
        self._client = genai.Client(api_key=settings.gemini_key_value)
        self._types = __import__("google.genai", fromlist=["types"]).types

    def _generate(self, prompt: str, schema: type[BaseModel] | None, system: str | None):
        config: dict[str, Any] = {"temperature": 0.2}
        if system:
            config["system_instruction"] = system
        if schema is not None:
            config["response_schema"] = schema
            config["response_mime_type"] = "application/json"
        try:
            return self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._types.GenerateContentConfig(**config),
            )
        except Exception as exc:  # SDK raises google.genai errors of many kinds
            retryable = any(
                token in type(exc).__name__ + str(exc).lower()
                for token in ("resourc exhaust", "429", "500", "503", "timeout", "internal")
            )
            raise LLMError(f"gemini call failed: {exc}", retryable=retryable) from exc

    def _complete_structured(self, prompt, schema, system) -> dict:
        response = self._generate(prompt, schema, system)
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return parsed.model_dump(mode="json") if isinstance(parsed, BaseModel) else dict(parsed)
        text = (response.text or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"gemini returned non-JSON: {text[:120]}", retryable=True) from exc

    def _complete_text(self, prompt, system) -> str:
        response = self._generate(prompt, None, system)
        if not response.text:
            raise LLMError("gemini returned an empty response", retryable=True)
        return response.text


class OllamaProvider(LLM):
    """Local Ollama server (http://localhost:11434) — free, no key required."""

    name = "ollama"

    def __init__(self) -> None:
        super().__init__()
        self.base_url = get_settings().ollama_base_url.rstrip("/")

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"ollama unreachable at {self.base_url}: {exc}", retryable=True) from exc

    def _complete_structured(self, prompt, schema, system) -> dict:
        payload = {
            "model": self.model,
            "messages": self._messages(prompt, system),
            "format": schema.model_json_schema(),
            "stream": False,
        }
        content = self._post(payload).get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"ollama returned non-JSON: {content[:120]}", retryable=True) from exc

    def _complete_text(self, prompt, system) -> str:
        payload = {"model": self.model, "messages": self._messages(prompt, system), "stream": False}
        return self._post(payload).get("message", {}).get("content", "")

    @staticmethod
    def _messages(prompt: str, system: str | None) -> list[dict[str, str]]:
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        return messages


class FakeLLM(LLM):
    """Deterministic offline provider: schema-valid canned data, zero network.

    Lets every test and notebook run with LLM_PROVIDER=fake. Answers are stable
    for a given prompt, so caching and determinism tests are meaningful.
    """

    name = "fake"

    def __init__(self) -> None:
        super().__init__()
        self.model = "fake"

    def _complete_structured(self, prompt, schema, system) -> dict:
        return _canned(schema, prompt)

    def _complete_text(self, prompt, system) -> str:
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
}


def _canned(schema: type[BaseModel], prompt: str) -> dict[str, Any]:
    """Build a deterministic, schema-valid dict for any Pydantic schema."""
    canned = _CANNED.get(schema.__name__)
    if canned is not None:
        data = dict(canned)
        # Keep fake output valid even if the schema changes fields later.
        data = {k: v for k, v in data.items() if k in schema.model_fields}
    else:
        data = {}
    for name, field in schema.model_fields.items():
        if name not in data:
            data[name] = _default_for(field.annotation, name, depth=0)
    logger.debug(
        "fake LLM produced %s (prompt hash %s)",
        schema.__name__,
        hashlib.sha1(prompt.encode()).hexdigest()[:8],
    )
    return data


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
