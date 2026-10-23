# Central configuration: every model name, key, threshold and path comes from
# .env (or defaults below) via pydantic-settings. Nothing is hardcoded elsewhere.
# Called by: every module (via get_settings()) and all notebooks.

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# We only ever use PyTorch. When tensorflow is installed (for other projects),
# sentence-transformers would otherwise load transformers' TF backend, which is
# slow to start and clashes with Keras 3. Setting USE_TF=no disables it cleanly.
# Must run before transformers is imported anywhere.
os.environ.setdefault("USE_TF", "no")

# ai/ directory — data/, notebooks/ and tests/ live next to the package.
AI_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """All runtime settings. Override any field with an env var of the same name."""

    model_config = SettingsConfigDict(
        env_file=[AI_ROOT / ".env", AI_ROOT.parent / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM providers ------------------------------------------------------
    llm_provider: Literal["gemini", "ollama", "fake"] = "fake"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.8-flash"
    # Tried ONCE when the primary model keeps failing on transient errors
    # (5xx / timeouts) after its retries. Empty string disables the fallback.
    gemini_fallback_model: str = "gemini-3.5-flash"
    # Latency controls: no thinking (0 = cheapest/fastest; -1 = never send the
    # config at all), and a hard cap on the answer size in tokens.
    gemini_thinking_budget: int = 0
    gemini_max_output_tokens: int = 2048
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    # Live opt-in (RUN_LIVE_LLM=1 in the shell): False keeps every run offline —
    # no live LLM call, no detail-page fetch. Read by the notebooks' cost gate
    # and by ingestion's detail fetch.
    run_live_llm: bool = False

    # --- Web discovery ------------------------------------------------------
    tavily_api_key: SecretStr = SecretStr("")
    tavily_max_results: int = 5
    # Hard per-run caps on REMOTE calls (free-tier protection; disk-cache
    # hits are always allowed and never counted against these limits).
    tavily_max_searches_per_run: int = 5
    max_extractions_per_run: int = 20
    # Accepted RSS entry with no deadline -> fetch its detail page and
    # re-extract once, at most this many times per run (free-tier protection).
    max_detail_fetches_per_run: int = 5
    # Feed bodies are cut to this many chars before the LLM (summaries are long).
    feed_text_max_chars: int = 6000
    # Polite crawling: one clear identity + a pause between HTTP requests.
    user_agent: str = "OppRadarBot/0.1 (student project; https://github.com/Riad-Doukha/OppRadar)"
    fetch_delay_seconds: float = 1.5
    fetch_timeout_seconds: float = 15.0
    respect_robots: bool = True

    # --- Embeddings ---------------------------------------------------------
    # `fake` = deterministic local hashing encoder (tests/offline, no model
    # download); `sentence_transformers` = the real local model below.
    embedding_provider: Literal["sentence_transformers", "fake"] = "sentence_transformers"
    embedding_model: str = "BAAI/bge-m3"
    embedding_fallback_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_batch_size: int = 32

    # --- OCR (documents/reader.py) -------------------------------------------
    ocr_dpi: int = 220  # page render resolution for rapidocr (higher = better, slower)
    ocr_text_score: float = 0.3  # drop OCR lines below this confidence (rapidocr default 0.5)

    # --- Thresholds ---------------------------------------------------------
    confidence_threshold: float = 0.65
    notify_threshold: float = 70.0
    semantic_weight: float = 0.5
    criteria_weight: float = 0.35
    bonus_weight: float = 0.15
    # rapidfuzz score (0-100) a profile word needs to count as satisfying a
    # requirement of an opportunity (matching/criteria.py).
    criteria_fuzzy_threshold: float = 85.0
    # Minimum cosine similarity before "your background matches this offer" is
    # worth saying as a reason (below it, only skill overlap is mentioned).
    reason_min_similarity: float = 0.3
    scanned_text_min_chars: int = 200

    # --- Notifications ------------------------------------------------------
    daily_instant_cap: int = 5
    quiet_hours_start: int = 22
    quiet_hours_end: int = 8
    digest_mode: Literal["instant", "daily", "weekly"] = "instant"

    # --- Agent ---------------------------------------------------------------
    agent_interval_seconds: int = 3600
    demo_interval_seconds: int = 10

    # --- Cost control --------------------------------------------------------
    llm_min_delay_seconds: float = 1.0
    llm_max_retries: int = 4
    llm_retry_base_wait: float = 2.0
    llm_max_input_chars: int = 8000
    # One call per match >= NOTIFY_THRESHOLD would burn the free tier: only the
    # best matches get their rule-generated reasons rephrased by the LLM.
    max_phrases_per_run: int = 5

    # --- Logging ---------------------------------------------------------------
    log_level: str = "INFO"

    # --- Paths (overridable, default under ai/data/) ---------------------------
    data_dir: Path = AI_ROOT / "data"

    @property
    def cache_dir(self) -> Path:
        """LLM / Tavily / embedding caches (git-ignored)."""
        return self.data_dir / "cache"

    @property
    def samples_dir(self) -> Path:
        return self.data_dir / "samples"

    @property
    def fixtures_dir(self) -> Path:
        return self.data_dir / "fixtures"

    @property
    def sources_path(self) -> Path:
        """Curated real-world sources (sources.yaml, committed)."""
        return self.data_dir / "sources.yaml"

    @property
    def live_feed_dir(self) -> Path:
        return self.data_dir / "live_feed"

    @property
    def eval_dir(self) -> Path:
        return self.data_dir / "eval"

    @property
    def store_dir(self) -> Path:
        """Local JSON storage (users, opportunities, matches, ...)."""
        return self.data_dir / "store"

    @property
    def prompts_dir(self) -> Path:
        return AI_ROOT / "oppradar_ai" / "prompts"

    @property
    def gemini_key_value(self) -> str:
        return self.gemini_api_key.get_secret_value()

    @property
    def tavily_key_value(self) -> str:
        return self.tavily_api_key.get_secret_value()

    @field_validator("run_live_llm", mode="before")
    @classmethod
    def _empty_is_off(cls, value: object) -> object:
        """`RUN_LIVE_LLM=` (empty) in a shell means "off", not a config error.

        Example:
            >>> Settings._empty_is_off("")
            False
            >>> Settings._empty_is_off("1")
            '1'
        """
        return False if value in ("", None) else value

    @model_validator(mode="after")
    def _check_weights(self) -> Settings:
        total = self.semantic_weight + self.criteria_weight + self.bonus_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scoring weights must sum to 1.0, got {total:.2f}")
        if not (0 <= self.quiet_hours_start <= 23 and 0 <= self.quiet_hours_end <= 23):
            raise ValueError("quiet hours must be 0-23")
        return self

    def ensure_dirs(self) -> Settings:
        """Create the data directories that are safe to commit or git-ignored."""
        for path in (self.data_dir, self.cache_dir, self.live_feed_dir, self.store_dir):
            path.mkdir(parents=True, exist_ok=True)
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; call .model_copy() to mutate)."""
    return Settings()


@contextmanager
def forced_provider(name: str) -> Iterator[None]:
    """Temporarily force LLM_PROVIDER for this process, then restore it.

    Used where a document must NEVER reach a remote model (a user's own CV):
    reading and extraction inside this block run with `name` whatever .env says.

    Example:
        >>> with forced_provider("fake"):   # doctest: +SKIP
        ...     get_settings().llm_provider
        'fake'
    """
    previous = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = name
    get_settings.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous
        get_settings.cache_clear()


def setup_logging(level: str | None = None, rapidocr_level: str = "WARNING") -> None:
    """Configure a readable root logger for scripts and notebooks.

    Third-party OCR chatter stays quiet by default; pass `rapidocr_level` to
    see it (e.g. when debugging the OCR pipeline).

    Example:
        >>> setup_logging("INFO")
    """
    import logging

    logging.basicConfig(
        level=level or get_settings().log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logging.getLogger("RapidOCR").setLevel(rapidocr_level)
