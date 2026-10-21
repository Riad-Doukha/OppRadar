import pytest
from pydantic import ValidationError

from oppradar_ai.config import Settings, get_settings


def test_default_provider_is_fake():
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "fake"


def test_settings_validate_weights():
    with pytest.raises(ValidationError, match="sum to 1.0"):
        Settings(_env_file=None, semantic_weight=0.9, criteria_weight=0.3, bonus_weight=0.1)


def test_settings_validate_quiet_hours():
    with pytest.raises(ValidationError, match="quiet hours"):
        Settings(_env_file=None, quiet_hours_start=99)


def test_paths_derive_from_data_dir(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert settings.cache_dir == tmp_path / "cache"
    assert settings.store_dir == tmp_path / "store"
    assert settings.samples_dir == tmp_path / "samples"
    assert settings.prompts_dir.name == "prompts"


def test_ensure_dirs_creates_directories(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path / "d").ensure_dirs()
    assert settings.cache_dir.is_dir()
    assert settings.store_dir.is_dir()
    assert settings.live_feed_dir.is_dir()


def test_secret_values_hidden_in_repr():
    settings = Settings(_env_file=None, gemini_api_key="secret-key-123")
    assert "secret-key-123" not in repr(settings)
    assert settings.gemini_key_value == "secret-key-123"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
