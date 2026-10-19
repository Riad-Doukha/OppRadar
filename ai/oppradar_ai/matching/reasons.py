"""Human-readable explanations for a match.

Every MatchResult ships 2-4 of these — the UI shows them instead of a bare
number, because "87%" alone doesn't tell an applicant anything.
"""

from __future__ import annotations

from datetime import date

from oppradar_ai.schemas import Opportunity, Profile

DAYS_SOON = 14


def build_reasons(
    profile: Profile,
    opportunity: Opportunity,
    *,
    similarity: float = 0.0,
    matched_skills: list[str] | None = None,
    today: date | None = None,
) -> list[str]:
    """Generate short, specific reasons this opportunity surfaced for this profile."""
    today = today or date.today()
    reasons: list[str] = []

    # Skills — the strongest, most concrete signal.
    matched_skills = matched_skills if matched_skills is not None else []
    if matched_skills:
        shown = ", ".join(matched_skills[:5])
        more = f" (+{len(matched_skills) - 5} more)" if len(matched_skills) > 5 else ""
        reasons.append(f"Matches your skills: {shown}{more}")

    # Semantic closeness.
    if similarity >= 0.75:
        reasons.append("Very close to your profile and interests")
    elif similarity >= 0.5:
        reasons.append("Related to your background")

    # Deadline pressure — helpful, not pushy.
    if opportunity.deadline is not None:
        days_left = (opportunity.deadline - today).days
        if 0 <= days_left <= DAYS_SOON:
            reasons.append(f"Closes soon — {days_left} day{'s' if days_left != 1 else ''} left")
        elif days_left > DAYS_SOON:
            reasons.append(f"Deadline: {opportunity.deadline.isoformat()}")

    # Format / location.
    if opportunity.mode is not None:
        if profile.preferences.modes and opportunity.mode in profile.preferences.modes:
            reasons.append(f"{opportunity.mode.value.capitalize()} — matches your preference")
        else:
            reasons.append(opportunity.mode.value.capitalize())

    # Type preference explicitly satisfied.
    if profile.preferences.types and opportunity.type in profile.preferences.types:
        reasons.append(f"A {opportunity.type.value}, one of the types you want")

    if not reasons:
        reasons.append("General fit based on your profile")

    return reasons[:4]
