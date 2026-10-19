"""SHARED LLM client — the only place in the AI package that talks to an LLM.

Any OpenAI-compatible endpoint works (OpenAI, Azure, Ollama, vLLM…). Configure
via environment / .env:

    LLM_API_KEY       required for chat; embeddings too unless backend=local
    LLM_BASE_URL      default https://api.openai.com/v1
    LLM_MODEL         default gpt-4o-mini
    EMBEDDING_MODEL   default text-embedding-3-small

⚠️  Shared file — both AI owners must approve changes.

Usage:

    from oppradar_ai.llm import chat, chat_json, embed, is_configured

    reply = chat([{"role": "user", "content": "hi"}])
    data  = chat_json([{"role": "user", "content": "return {}"}])
    vecs  = embed(["hello", "world"])
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, TypeVar

import httpx

from oppradar_ai.errors import LLMError

T = TypeVar("T")

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3


def _config() -> tuple[str, str, str, str]:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
    embedding_model = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return api_key, base_url, model, embedding_model


def is_configured() -> bool:
    """True when a usable LLM key is present."""
    return bool(_config()[0])


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_key, base_url, _, _ = _config()
    if not api_key:
        raise LLMError("LLM_API_KEY is not set — see .env.example")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.post(
                f"{base_url}{path}",
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        except httpx.HTTPError as exc:  # network problem — worth a retry
            last_error = exc
            time.sleep(2**attempt)
            continue

        if response.status_code == 200:
            return response.json()

        detail = f"HTTP {response.status_code}: {response.text[:300]}"
        if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
            last_error = LLMError(detail)
            time.sleep(2**attempt)
            continue
        raise LLMError(detail)

    raise LLMError(f"LLM request failed after {MAX_RETRIES} attempts: {last_error}")


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    """Plain chat completion. `messages` = [{"role": ..., "content": ...}]."""
    _, _, model, _ = _config()
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = _post("/chat/completions", body)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"unexpected response shape: {exc}") from exc


def chat_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Chat completion that must return a JSON object (json_mode on)."""
    raw = chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    # Models sometimes wrap JSON in ```json fences despite json_mode.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        cleaned = cleaned.removeprefix("json").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model did not return valid JSON: {exc}; got: {raw[:200]}") from exc
    if not isinstance(parsed, dict):
        raise LLMError("expected a JSON object from the model")
    return parsed


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Empty input returns [] without an API call."""
    texts = [t for t in texts if t and t.strip()]
    if not texts:
        return []
    _, _, _, embedding_model = _config()
    data = _post("/embeddings", {"model": embedding_model, "input": texts})
    try:
        rows = sorted(data["data"], key=lambda d: d["index"])
        return [row["embedding"] for row in rows]
    except (KeyError, TypeError) as exc:
        raise LLMError(f"unexpected embeddings response: {exc}") from exc
