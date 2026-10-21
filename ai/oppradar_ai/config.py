# Central configuration: every model name, key, threshold and path comes from
# .env (or defaults below) via pydantic-settings. Nothing is hardcoded elsewhere.
# Called by: every module (via get_settings()) and all notebooks.

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
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
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # --- Web discovery ------------------------------------------------------
    tavily_api_key: SecretStr = SecretStr("")
    tavily_max_results: int = 5

    # --- Embeddings ---------------------------------------------------------
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
