"""Hard filters — constraints the opportunity must satisfy.

Anything failing one of these is dropped (never scored), so semantics can't
override a hard requirement like a closing date in the past.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from oppradar_ai.schemas import Opportunity, Profile


@dataclass
class FilterResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)  # why it was rejected


def hard_filters(
    profile: Profile,
    opportunity: Opportunity,
    *,
    today: date | None = None,
) -> FilterResult:
    """Check the opportunity against the profile's preferences.

    Preferences that are empty mean "no preference" and always pass.
    """
    today = today or date.today()
    failures: list[str] = []

    # 1. Deadline in the past → dead opportunity
    if opportunity.deadline is not None and opportunity.deadline < today:
        failures.append(f"deadline passed ({opportunity.deadline.isoformat()})")

    prefs = profile.preferences

    # 2. Mode preference (remote / hybrid / onsite)
    if prefs.modes and opportunity.mode is not None and opportunity.mode not in prefs.modes:
        failures.append(f"mode {opportunity.mode.value} not in your preferences")

    # 3. Country preference
    if prefs.countries and opportunity.country:
        if opportunity.country.lower() not in {c.lower() for c in prefs.countries}:
            failures.append(f"{opportunity.country} not in your preferred countries")

    # 4. Opportunity-type preference
    if prefs.types and opportunity.type not in prefs.types:
        failures.append(f"{opportunity.type.value} opportunities are not what you're looking for")

    return FilterResult(passed=not failures, reasons=failures)
