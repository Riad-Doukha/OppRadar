"""Prompt templates for the assistant.

The system prompt lives in system.md so it can be iterated on without touching
code; build_user_prompt() grounds each question in the retrieved opportunities.
"""

from __future__ import annotations

from pathlib import Path

from oppradar_ai.schemas import Opportunity, Profile

_SYSTEM_FILE = Path(__file__).with_name("system.md")
SYSTEM_PROMPT = _SYSTEM_FILE.read_text(encoding="utf-8").strip()

_CITE_BLOCK = """[{i}] {title}
    organization: {organization}
    type: {type} | mode: {mode} | location: {location} | deadline: {deadline}
    tags: {tags}
    url: {url}
    ---"""


def build_user_prompt(
    question: str,
    opportunities: list[Opportunity],
    *,
    profile: Profile | None = None,
) -> str:
    """Ground the question in the retrieved opportunities (and the profile)."""
    lines: list[str] = []

    if profile is not None:
        lines.append("The user's profile:")
        if profile.headline:
            lines.append(f"- headline: {profile.headline}")
        if profile.skills:
            lines.append(f"- skills: {', '.join(profile.skills[:15])}")
        if profile.preferences.types:
            lines.append(
                "- looking for: " + ", ".join(t.value for t in profile.preferences.types)
            )
        lines.append("")

    if opportunities:
        lines.append("Retrieved opportunities (the ONLY ones you may cite):")
        for i, opp in enumerate(opportunities, start=1):
            lines.append(
                _CITE_BLOCK.format(
                    i=i,
                    title=opp.title,
                    organization=opp.organization,
                    type=opp.type.value,
                    mode=opp.mode.value if opp.mode else "?",
                    location=opp.location or "?",
                    deadline=opp.deadline.isoformat() if opp.deadline else "?",
                    tags=", ".join(opp.tags) or "-",
                    url=opp.source_url,
                )
            )
    else:
        lines.append("No opportunities were retrieved for this question.")

    lines.append("")
    lines.append(f"Question: {question}")
    return "\n".join(lines)
