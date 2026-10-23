# Hard filters: opportunities that cannot fit this profile are removed BEFORE any
# embedding or LLM work (expired, scam-flagged, against the stated preferences).
# Called by: matching/composer.py, notebooks. Rule: missing data never filters —
# only contradicting data does (unknown country/mode stays, flagged, like null deadlines).

from __future__ import annotations

import logging
from datetime import date

from oppradar_ai.schemas import (
    DroppedOpportunity,
    DropReason,
    FilterOutcome,
    Opportunity,
    Preferences,
    Profile,
    TrustLevel,
)

logger = logging.getLogger(__name__)

# What a source writes when it does not state the country ("Unknown", "Global").
_OPEN_COUNTRIES = frozenset({"", "unknown", "n/a", "na", "-", "none", "global", "worldwide", "any"})


def apply_hard_filters(
    profile: Profile,
    opportunities: list[Opportunity],
    *,
    today: date | None = None,
) -> FilterOutcome:
    """Split opportunities into (kept, dropped-with-reason) for one profile.

    Example:
        >>> outcome = apply_hard_filters(profile, [expired, matching_internship])
        >>> len(outcome.passed), [d.reason.value for d in outcome.dropped]
        (1, ['expired'])
    """
    today = today or date.today()
    outcome = FilterOutcome()
    for opportunity in opportunities:
        decision = drop_reason(profile, opportunity, today=today)
        if decision is None:
            outcome.passed.append(opportunity)
            continue
        reason, detail = decision
        outcome.dropped.append(
            DroppedOpportunity(
                opportunity_id=opportunity.id,
                title=opportunity.title,
                reason=reason,
                detail=detail,
            )
        )
    logger.info(
        "hard filters for %s: %d kept, %d dropped of %d",
        profile.user_id,
        len(outcome.passed),
        len(outcome.dropped),
        len(opportunities),
    )
    return outcome


def drop_reason(
    profile: Profile,
    opportunity: Opportunity,
    *,
    today: date | None = None,
) -> tuple[DropReason, str] | None:
    """Why this opportunity is dropped for this profile (None = it stays).

    Example:
        >>> drop_reason(profile, expired)[0]
        <DropReason.EXPIRED: 'expired'>
        >>> drop_reason(profile, matching_internship) is None
        True
    """
    today = today or date.today()
    if opportunity.deadline is not None and opportunity.deadline < today:
        return DropReason.EXPIRED, f"deadline {opportunity.deadline.isoformat()} has passed"
    if opportunity.trust_level is TrustLevel.SCAM or opportunity.scam_flags:
        flags = ", ".join(flag.flag.value for flag in opportunity.scam_flags)
        return DropReason.SCAM, f"scam indicators: {flags or 'trust level = scam'}"
    return _preference_reason(profile, opportunity)


def _preference_reason(profile: Profile, opportunity: Opportunity) -> tuple[DropReason, str] | None:
    """Check the four preferences the user declared (types, modes, countries, funding)."""
    prefs = profile.preferences
    if prefs.types and opportunity.type not in prefs.types:
        wanted = ", ".join(kind.value for kind in prefs.types)
        detail = f"{opportunity.type.value} is not one of your types ({wanted})"
        return DropReason.TYPE_MISMATCH, detail
    if prefs.modes and opportunity.mode is not None and opportunity.mode not in prefs.modes:
        wanted = ", ".join(prefs.modes)
        return DropReason.MODE_MISMATCH, f"{opportunity.mode} is not one of your modes ({wanted})"
    country = _normalize(opportunity.country)
    if prefs.countries and country not in _OPEN_COUNTRIES and not _country_matches(prefs, country):
        wanted = ", ".join(prefs.countries)
        detail = f"{opportunity.country} is not one of your countries ({wanted})"
        return DropReason.COUNTRY_MISMATCH, detail
    if prefs.needs_funding and not (opportunity.funding or "").strip():
        return DropReason.NO_FUNDING, "your profile needs funding and this listing states none"
    return None


def _country_matches(prefs: Preferences, country: str) -> bool:
    """Case-insensitive country match ('Algeria' == 'algeria')."""
    wanted = (_normalize(value) for value in prefs.countries)
    return any(value == country or value in country or country in value for value in wanted)


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()
