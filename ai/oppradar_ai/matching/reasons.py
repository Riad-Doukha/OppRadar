# Match reasons: the RULES write them (always available, always explainable) and
# the LLM only rephrases them for matches >= notify_threshold — same count, same
# facts, never a CV. Called by: matching/composer.py and the notebooks.

from __future__ import annotations

import logging

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.llm import LLM, LLMError
from oppradar_ai.matching.criteria import best_match, normalize_word
from oppradar_ai.matching.texts import opportunity_text
from oppradar_ai.schemas import (
    CriteriaStatus,
    EligibilityCriterion,
    Opportunity,
    PhrasedReasons,
    Profile,
)

logger = logging.getLogger(__name__)

PROMPT_FILE = "match_reasons.md"
EMPTY_PROFILE_NOTE = (
    "Your profile is empty — add skills, education and languages to raise this score"
)
# A bonus signal only becomes a reason when it is fully satisfied (1.0), never
# when it is neutral (0.5) or missed (0.0): no threshold, no guessing.
_SIGNAL_TEXT = {
    "funding": "Funding is offered",
    "language": "The offer's language matches yours",
    "trust": "Verified organizer",
}


def rule_reasons(
    profile: Profile,
    opportunity: Opportunity,
    *,
    similarity: float,
    criteria: list[EligibilityCriterion],
    signals: list[tuple[str, float]],
    settings: Settings | None = None,
) -> list[str]:
    """Up to three rule-generated reasons, ranked by their contribution to the score.

    Example:
        >>> rule_reasons(profile, opportunity, similarity=0.0, criteria=[], signals=[])[0]
        'Deadline 2026-12-05 (as stated in the source)'
    """
    settings = settings or get_settings()
    candidates = _criteria_reasons(criteria, settings)
    candidates += _similarity_reason(profile, opportunity, similarity, settings)
    candidates += [
        (settings.bonus_weight * value, _SIGNAL_TEXT[name])
        for name, value in signals
        if value >= 1.0 and name in _SIGNAL_TEXT
    ]
    candidates.sort(key=lambda item: item[0], reverse=True)  # stable: ties keep the build order
    reasons = [text for _, text in candidates[:3]]
    if profile_is_empty(profile):
        reasons.insert(0, EMPTY_PROFILE_NOTE)
    return reasons[:3] or _fallback_reasons(opportunity)


def phrase_reasons(
    reasons: list[str],
    opportunity: Opportunity,
    llm: LLM,
    *,
    settings: Settings | None = None,
) -> list[str]:
    """Let the model reword the RULE reasons — same count, same facts, no profile.

    The prompt carries only the short reason lines and the opportunity's public
    title/organizer: never a CV, a name or any contact data.

    Example:
        >>> phrase_reasons(["Requirement met: Python"], opportunity, fake_llm)[0][:1]
        '['
    """
    if not reasons:
        return []
    settings = settings or get_settings()
    system = (settings.prompts_dir / PROMPT_FILE).read_text(encoding="utf-8")
    try:
        answer = llm.structured(_prompt(reasons, opportunity), PhrasedReasons, system=system)
    except LLMError as exc:
        logger.warning("phrasing failed, keeping the rule reasons: %s", exc)
        return list(reasons)
    return _fit(answer.reasons, reasons)


def phrasing_allowed(settings: Settings | None = None) -> bool:
    """True only when a real provider may be called to reword reasons.

    Example:
        >>> phrasing_allowed(Settings(llm_provider="fake", run_live_llm=True))
        False
        >>> phrasing_allowed(Settings(llm_provider="gemini", run_live_llm=False))
        False
    """
    settings = settings or get_settings()
    return settings.run_live_llm and settings.llm_provider != "fake"


def profile_is_empty(profile: Profile) -> bool:
    """True when the profile says nothing at all about the person."""
    return not any(
        (
            profile.summary,
            profile.headline,
            profile.country,
            profile.skills,
            profile.interests,
            profile.languages,
            profile.education,
            profile.experience,
            profile.projects,
        )
    )


def _criteria_reasons(
    criteria: list[EligibilityCriterion], settings: Settings
) -> list[tuple[float, str]]:
    """One reason per met requirement, each worth its share of the criteria part."""
    met = [c for c in criteria if c.status is CriteriaStatus.MET]
    checked = sum(1 for c in criteria if c.status in (CriteriaStatus.MET, CriteriaStatus.MISSED))
    if not met or not checked:
        return []
    share = settings.criteria_weight / checked
    return [(share, f"Requirement met: {c.text}") for c in met]


def _similarity_reason(
    profile: Profile, opportunity: Opportunity, similarity: float, settings: Settings
) -> list[tuple[float, str]]:
    """The overlap between the profile's skills and the listing's own text."""
    listing = normalize_word(opportunity_text(opportunity))
    shared = [skill for skill in profile.skills if best_match(skill, listing)][:3]
    weight = settings.semantic_weight * similarity
    if shared:
        return [(weight, f"Uses skills you list: {', '.join(shared)}")]
    if similarity >= settings.reason_min_similarity:
        return [(weight, f"Profile background matches this offer ({similarity:.0%})")]
    return []


def _fallback_reasons(opportunity: Opportunity) -> list[str]:
    """Facts of the listing itself, when nothing about the profile could be matched."""
    facts: list[str] = []
    if opportunity.deadline:
        facts.append(f"Deadline {opportunity.deadline.isoformat()} (as stated in the source)")
    else:
        facts.append("No deadline in the source — verify it on the page")
    where = ", ".join(
        part for part in (opportunity.country, opportunity.location, opportunity.mode) if part
    )
    if where:
        facts.append(f"{opportunity.type.value.capitalize()} — {where}")
    if opportunity.funding:
        facts.append(f"Funding: {opportunity.funding}")
    return facts[:3]


def _fit(phrased: list[str], original: list[str]) -> list[str]:
    """Same length as the rules' list: never lose a reason, never invent a fact."""
    kept = [text.strip() for text in phrased if text.strip()][: len(original)]
    return kept + original[len(kept) :]


def _prompt(reasons: list[str], opportunity: Opportunity) -> str:
    listed = "\n".join(f"- {reason}" for reason in reasons)
    return (
        f"Opportunity: {opportunity.title} — {opportunity.organizer}\n"
        f"Rule-generated reasons (every fact is already verified by the rules):\n{listed}"
    )
