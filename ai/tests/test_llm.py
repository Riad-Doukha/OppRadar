import pytest

from oppradar_ai import llm
from oppradar_ai.llm import (
    DiskCache,
    FakeLLM,
    LLMError,
    get_llm,
    get_stats,
    reset_stats,
)
from oppradar_ai.schemas import Opportunity, Profile


@pytest.fixture(autouse=True)
def _clean_stats():
    reset_stats()
    yield
    reset_stats()


def test_get_llm_returns_fake_by_default():
    assert isinstance(get_llm("fake"), FakeLLM)


def test_get_llm_unknown_provider():
    with pytest.raises(LLMError, match="unknown LLM provider"):
        get_llm("claude")


def test_fake_structured_returns_valid_model():
    result = get_llm("fake").structured(
        "Extract an opportunity from: ML intern at Acme.", Opportunity
    )
    assert isinstance(result, Opportunity)
    assert result.title  # canned, but valid


def test_fake_is_deterministic():
    fake = get_llm("fake")
    first = fake.structured("same prompt", Opportunity)
    second = fake.structured("same prompt", Opportunity)
    assert first == second


def test_cache_hit_on_second_call():
    fake = get_llm("fake")
    fake.structured("cache me", Profile)
    assert get_stats().calls == 1 and get_stats().cached == 0
    fake.structured("cache me", Profile)
    assert get_stats().calls == 1 and get_stats().cached == 1


def test_cache_key_depends_on_model_and_prompt():
    k1 = DiskCache.key("fake", "m1", "hello", "Opportunity")
    k2 = DiskCache.key("fake", "m2", "hello", "Opportunity")
    k3 = DiskCache.key("fake", "m1", "hello!", "Opportunity")
    k4 = DiskCache.key("fake", "m1", "hello", "Profile")
    assert len({k1, k2, k3, k4}) == 4


def test_text_is_cached():
    fake = get_llm("fake")
    answer = fake.text("what is OppRadar?")
    assert isinstance(answer, str) and answer
    fake.text("what is OppRadar?")
    assert get_stats().cached == 1


def test_long_input_is_truncated():
    fake = get_llm("fake")
    long_prompt = "x" * (fake.max_input_chars + 500)
    truncated = fake._truncate(long_prompt)
    assert len(truncated) < len(long_prompt)
    assert truncated.endswith("[...truncated...]")


def test_gemini_requires_key():
    # Build a keyless config directly so the test passes even when the developer
    # has a real GEMINI_API_KEY in ai/.env.
    from oppradar_ai.config import Settings

    keyless = Settings(_env_file=None, gemini_api_key="")
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        llm.GeminiProvider(settings=keyless)


def test_disk_cache_put_get_roundtrip():
    cache = DiskCache()
    cache.put("unit-test-key", {"text": "hi"})
    assert cache.get("unit-test-key") == {"text": "hi"}
