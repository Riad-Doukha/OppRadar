# Text builders: the two strings the embedder compares (profile vs opportunity).
# Called by: matching/composer.py and matching/reasons.py — both sides are built
# here so similarity is always measured the same way.

from __future__ import annotations

from oppradar_ai.schemas import EducationItem, ExperienceItem, Opportunity, Profile


def profile_text(profile: Profile) -> str:
    """The user's BACKGROUND as one text — never their preferences or contact data.

    Preferences already act as hard filters; putting them here would count the
    same signal twice (once as a filter, once as similarity).

    Example:
        >>> profile_text(Profile(skills=["python"], summary="Data student"))
        'Data student skills: python'
    """
    parts = [
        profile.headline.strip(),
        profile.summary.strip(),
        _label("skills", profile.skills),
        _label("interests", profile.interests),
        _label("languages", profile.languages),
        _label("country", [profile.country] if profile.country.strip() else []),
        _label("education", [_education(e) for e in profile.education]),
        _label("experience", [_experience(e) for e in profile.experience]),
        _label("projects", [project.name for project in profile.projects]),
    ]
    return " ".join(part for part in parts if part).strip()


def opportunity_text(opportunity: Opportunity) -> str:
    """Everything public about one listing as a single text to embed.

    Example:
        >>> opportunity_text(Opportunity(title="ML Intern", organizer="Ooredoo"))
        'ML Intern organizer: Ooredoo type: other'
    """
    location = ", ".join(
        place for place in (opportunity.location.strip(), opportunity.country.strip()) if place
    )
    parts = [
        opportunity.title.strip(),
        _label("organizer", [opportunity.organizer]),
        f"type: {opportunity.type.value}",
        _label("summary", [opportunity.summary.strip()] if opportunity.summary.strip() else []),
        _label("eligibility", opportunity.eligibility),
        _label("benefits", opportunity.benefits),
        _label("funding", [opportunity.funding] if opportunity.funding else []),
        _label("mode", [opportunity.mode] if opportunity.mode else []),
        _label("location", [location] if location else []),
        _label("language", [opportunity.language] if opportunity.language else []),
    ]
    return " ".join(part for part in parts if part).strip()


def _label(name: str, items: list[str]) -> str:
    """`name: a, b` when there is something to show, '' otherwise."""
    clean = [item.strip() for item in items if item and item.strip()]
    return f"{name}: {', '.join(clean)}" if clean else ""


def _education(item: EducationItem) -> str:
    return ", ".join(part for part in (item.degree, item.field, item.institution) if part)


def _experience(item: ExperienceItem) -> str:
    return " at ".join(part for part in (item.title, item.organization) if part)
