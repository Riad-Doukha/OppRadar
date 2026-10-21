# RunBudget tests: limits come from settings, explicit caps stop calls,
# and a zero limit blocks every remote call (safe offline default).

from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.budget import RunBudget


def test_default_limits_come_from_settings() -> None:
    settings = get_settings()
    budget = RunBudget(settings)
    assert budget.searches.limit == settings.tavily_max_searches_per_run
    assert budget.extractions.limit == settings.max_extractions_per_run
    assert budget.searches.made == 0 and budget.extractions.made == 0


def test_allow_stops_at_the_cap() -> None:
    budget = RunBudget(max_searches=2, max_extractions=1)
    assert [budget.allow_search() for _ in range(3)] == [True, True, False]
    assert [budget.allow_extraction() for _ in range(2)] == [True, False]
    assert budget.searches.made == 2 and budget.extractions.made == 1


def test_zero_limit_blocks_every_remote_call() -> None:
    budget = RunBudget(max_searches=0, max_extractions=0)
    assert not budget.allow_search()
    assert not budget.allow_extraction()
    assert budget.searches.made == 0 and budget.extractions.made == 0


def test_explicit_caps_are_recorded_in_usage() -> None:
    budget = RunBudget(max_searches=7, max_extractions=3)
    assert budget.searches.limit == 7 and budget.extractions.limit == 3
    budget.allow_search()
    assert budget.searches.made == 1 and budget.extractions.made == 0
