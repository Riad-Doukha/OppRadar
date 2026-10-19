"""Heuristic scam detection.

Deterministic rules → a 0-1 risk score. An optional LLM second opinion runs
only on the ambiguous middle band (and only when configured).
"""

from __future__ import annotations

import re

from oppradar_ai import llm
from oppradar_ai.schemas import Opportunity, ScamLabel, ScamVerdict

SCAM_THRESHOLD = 0.6
SUSPICIOUS_THRESHOLD = 0.3

# (weight, compiled pattern, human-readable reason)
RULES: list[tuple[float, re.Pattern[str], str]] = [
    (0.35, re.compile(r"\b(pay|payment|deposit|fee)\b.{0,50}\b(application|apply|register|registration|sign.?up|seat)\b", re.I),
     "Asks for an application payment"),
    (0.30, re.compile(r"\b(send|transfer|western.?union|orange.?money|baridi.?mob)\b.{0,60}\b(money|cash|funds|fee|amount)\b", re.I),
     "Requests money transfer"),
    (0.25, re.compile(r"\b(passport|id card|bank details|rib)\b.{0,60}\b(send|whatsapp|email now)\b", re.I),
     "Urges you to send identity documents over chat"),
    (0.25, re.compile(r"\b\d{3,}\s?\$?(?:\s|\$)?(?:per week|/week|a week|weekly)\b", re.I),
     "Promises an implausible weekly income"),
    (0.20, re.compile(r"\b(urgent|last chance|act now|24h|48h)\b", re.I),
     "Urgency language"),
    (0.20, re.compile(r"\b(100%?\s*(guaranteed|guarantee)|easy money|earn \d{3,})\b", re.I),
     "Too-good-to-be-true promises"),
    (0.15, re.compile(r"\bno\s+(experience|skills)\s+needed\b", re.I),
     "\"No experience needed\" for a high-paying role"),
    (0.15, re.compile(r"(gmail|yahoo|outlook|hotmail)\.(com|fr|dz)\b", re.I),
     "Free-mail contact for an organisation"),
    (0.10, re.compile(r"(\$\s?\d{4,}|\d{4,}\s?€)", re.I),
     "Suspiciously large salary"),
]

EMOJI_RE = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F600-\U0001F64F]"
)
KNOWN_FREE_MAIL = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com")


def score_opportunity(opportunity: Opportunity) -> ScamVerdict:
    """Pure heuristic scoring — no network, fully deterministic."""
    text = f"{opportunity.title}\n{opportunity.description}\n{opportunity.source_url}"
    score = 0.0
    reasons: list[str] = []

    for weight, pattern, reason in RULES:
        if pattern.search(text):
            score += weight
            reasons.append(reason)

    emoji_count = len(EMOJI_RE.findall(opportunity.title))
    if emoji_count >= 4:
        score += 0.1
        reasons.append("Title is stuffed with emoji")

    if len(opportunity.description.strip()) < 40:
        score += 0.05
        reasons.append("Almost no description")

    if opportunity.deadline is None and opportunity.type.value == "job":
        score += 0.05
        reasons.append("No deadline for a paid role")

    score = round(min(score, 1.0), 3)
    if score >= SCAM_THRESHOLD:
        label = ScamLabel.SCAM
    elif score >= SUSPICIOUS_THRESHOLD:
        label = ScamLabel.SUSPICIOUS
    else:
        label = ScamLabel.SAFE
    return ScamVerdict(label=label, score=score, reasons=reasons)


LLM_PROMPT = """You are a scam analyst for job/scholarship postings. Given the posting,
decide whether it is a scam. Return ONLY JSON: {{"label": "safe"|"suspicious"|"scam",
"reasons": ["...", ...]}}.

Posting:
---
{posting}
---
"""


def _llm_second_opinion(opportunity: Opportunity, first: ScamVerdict) -> ScamVerdict:
    """LLM review for ambiguous cases only; merged with the heuristic score."""
    if not llm.is_configured():
        return first
    data = llm.chat_json(
        [
            {
                "role": "user",
                "content": LLM_PROMPT.format(
                    posting=f"{opportunity.title}\n{opportunity.description}"[:1500]
                ),
            }
        ]
    )
    label = str(data.get("label", first.label.value))
    reasons = [f"LLM: {r}" for r in data.get("reasons", [])][:4]
    if label == "scam":
        score = max(first.score, 0.75)
        merged = ScamLabel.SCAM
    elif label == "suspicious":
        score = max(first.score, SUSPICIOUS_THRESHOLD)
        merged = ScamLabel.SUSPICIOUS
    else:
        score = first.score  # heuristics win over an "all clear"
        merged = first.label
    return ScamVerdict(label=merged, score=round(score, 3), reasons=first.reasons + reasons)


def check(opportunity: Opportunity, *, use_llm: bool = True) -> ScamVerdict:
    """Score an opportunity for scam risk (interface #4 in docs/ai-interface.md)."""
    verdict = score_opportunity(opportunity)
    if (
        use_llm
        and verdict.label is ScamLabel.SUSPICIOUS
        and llm.is_configured()
    ):
        verdict = _llm_second_opinion(opportunity, verdict)
    return verdict
