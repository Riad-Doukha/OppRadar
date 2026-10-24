# Grounded chat: answer ONE question about ONE opportunity from its public record.
# Eligibility is computed locally (check_criteria) and only abstract requirement
# verdicts reach the model — never a CV or profile text. Pure: nothing is stored
# here (the UI persists turns). Called by: api.answer, chat_ui.py, notebook 06.

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from oppradar_ai.api import ApiError, extract_opportunity
from oppradar_ai.config import Settings, get_settings
from oppradar_ai.llm import QuotaExhausted, get_llm
from oppradar_ai.matching.criteria import check_criteria
from oppradar_ai.matching.reasons import phrasing_allowed
from oppradar_ai.schemas import (
    ChatAnswer,
    ChatTurn,
    Citation,
    CriteriaStatus,
    EligibilityAssessment,
    EligibilityCriterion,
    Opportunity,
    Profile,
)

logger = logging.getLogger(__name__)

PROMPT_FILE = "answer_question.md"
# The exact phrase every unanswerable question gets (the contract with Phase 7).
REFUSAL_PHRASE = "not in the source"

# A message this long is treated as a pasted announcement, not a question.
PASTE_MIN_CHARS = 400
# Input budget: the LLM layer cuts the END of an over-long prompt, so the question
# comes first, every field is capped and the oldest history turns are dropped first.
MAX_QUESTION_CHARS = 1500
MAX_TURN_CHARS = 500
MAX_FIELD_CHARS = 1000
MAX_LINE_CHARS = 240
MAX_LIST_ITEMS = 12

_NONE = "none stated"
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[a-z]{2,4})?$")

_WHY_OFF = (
    "Model answers are switched off (RUN_LIVE_LLM is not 1 or no real provider is "
    "configured), so this is a rules-only summary."
)
_WHY_QUOTA = (
    "The assistant model's quota is used up right now, so this is a rules-only summary."
)
_WHY_ERROR = "The assistant model could not be reached, so this is a rules-only summary."

_ASK_SOMETHING = (
    "Ask me about this opportunity — for example its deadline, funding or requirements."
)

_ATTACHMENT_NOTES = {
    "offline": "live page reading is off (it needs RUN_LIVE_LLM=1 and a real provider)",
    "fetch": "the page could not be downloaded",
    "rejected": "it does not look like a single opportunity announcement",
    "pending": "the model could not analyse it right now",
    "unusable": "it has no usable title or organizer",
}

_FRENCH_WORDS = frozenset(
    (
        "le", "la", "les", "un", "une", "des", "du", "de", "est", "sont", "quel", "quelle",
        "quels", "quelles", "quand", "comment", "combien", "pourquoi", "où", "ou", "et",
        "pour", "avec", "sans", "puis", "je", "suis", "dois", "peut", "que", "qui", "dans",
        "sur", "limite", "bourse", "candidature", "admissible",
    )
)
_ENGLISH_WORDS = frozenset(
    (
        "the", "is", "are", "what", "when", "how", "much", "many", "who", "where", "can",
        "do", "does", "for", "with", "and", "to", "of", "this", "that", "deadline", "apply",
        "am", "eligible", "funding", "requirements",
    )
)
_FRENCH_ACCENTS = frozenset("àâçéèêëîïôûùüÿœ")


@dataclass(frozen=True)
class _Evidence:
    """Everything the answer is built from: public record + abstract local verdicts."""

    opportunity: Opportunity
    record_text: str  # the public record as rendered for the model (= citation corpus)
    verdict_lines: str  # requirement-level outcomes only, no profile evidence
    assessment: EligibilityAssessment  # computed locally, attached to every answer
    unknown: tuple[str, ...]  # requirements the rules could not decide


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def answer(
    profile: Profile,
    opportunity: Opportunity | None,
    history: list[ChatTurn],
    message: str,
    *,
    settings: Settings | None = None,
) -> ChatAnswer:
    """Grounded answer to one message (frozen Phase-7 signature; stores nothing).

    The model sees only the public record, the question, recent turns and
    abstract requirement verdicts. Unanswerable questions say "not in the source"
    with `in_source=False`; a closed gate, a 429 or any model failure gives a
    rules-only answer. A URL or a long pasted text is extracted first and
    answered from, then returned as `extracted_opportunity`.

    Example:
        >>> reply = answer(profile, opportunity, [], "What is the deadline?")  # doctest: +SKIP
        >>> reply.in_source, reply.eligibility is not None
        (True, True)
    """
    settings = settings or get_settings()
    question = " ".join((message or "").split())
    if not question:
        return ChatAnswer(answer=_ASK_SOMETHING, in_source=True)
    extracted, notes = _read_attachment(message.strip(), settings)
    source = extracted or opportunity
    hint = detect_language(question)
    if source is None:
        return _no_source(notes)
    evidence = _build_evidence(profile, source)
    reply, why = _model_reply(evidence, history, question, hint, settings)
    if reply is None:
        reply = ChatAnswer(answer=_rules_text(evidence, why), in_source=True)
    return _finalize(reply, evidence, hint, extracted, notes)


def build_prompt(
    profile: Profile,
    opportunity: Opportunity,
    history: list[ChatTurn],
    message: str,
    *,
    settings: Settings | None = None,
) -> str:
    """The exact user prompt `answer()` would send — handy to prove what the model sees.

    Example:
        >>> "Requirement check" in build_prompt(profile, opp, [], "Deadline?")  # doctest: +SKIP
        True
    """
    settings = settings or get_settings()
    question = " ".join((message or "").split())
    evidence = _build_evidence(profile, opportunity)
    turns = _recent_turns(history, question, settings.chat_history_turns)
    budget = settings.llm_max_input_chars
    return _prompt(evidence, turns, question, detect_language(question), budget)


def model_allowed(settings: Settings | None = None) -> bool:
    """The chat cost gate: the offline fake is free; a real provider needs RUN_LIVE_LLM=1.

    Example:
        >>> model_allowed(Settings(llm_provider="fake"))
        True
        >>> model_allowed(Settings(llm_provider="gemini", run_live_llm=False))
        False
    """
    settings = settings or get_settings()
    return settings.llm_provider == "fake" or phrasing_allowed(settings)


def assess_eligibility(
    criteria: list[EligibilityCriterion], opportunity: Opportunity
) -> EligibilityAssessment:
    """Local verdict: False if any requirement is missed, True if all are met, else None.

    Example:
        >>> assess_eligibility([], opportunity).eligible is None   # doctest: +SKIP
        True
    """
    met = [c.text for c in criteria if c.status is CriteriaStatus.MET]
    gaps = [c.text for c in criteria if c.status is CriteriaStatus.MISSED]
    unknown = [c.text for c in criteria if c.status is CriteriaStatus.UNKNOWN]
    if gaps:
        eligible: bool | None = False
    else:
        eligible = True if criteria and not unknown else None
    steps = [f"Check whether you can close this gap: {text}" for text in gaps]
    steps += [f"Confirm with the organizer: {text}" for text in unknown]
    if not criteria:
        steps.append("The source states no requirements: confirm eligibility on the official page.")
    if opportunity.deadline:
        steps.append(f"Apply before {opportunity.deadline.isoformat()}.")
    return EligibilityAssessment(eligible=eligible, met=met, gaps=gaps, next_steps=steps[:5])


def detect_language(text: str) -> str:
    """Cheap offline guess of the user's language: `ar`, `fr` or `en` (a hint only).

    Example:
        >>> detect_language("Quelle est la date limite ?"), detect_language("What is it?")
        ('fr', 'en')
    """
    letters = [ch for ch in text if ch.isalpha()]
    if letters and sum("\u0600" <= ch <= "\u06ff" for ch in letters) / len(letters) > 0.3:
        return "ar"
    words = re.findall(r"[^\W\d_]+", text.casefold())
    french = sum(word in _FRENCH_WORDS for word in words) + sum(
        ch in _FRENCH_ACCENTS for ch in text.casefold()
    )
    english = sum(word in _ENGLISH_WORDS for word in words)
    return "fr" if french > english else "en"


# --------------------------------------------------------------------------- #
# Evidence: the public record + abstract local verdicts
# --------------------------------------------------------------------------- #
def _build_evidence(profile: Profile, opportunity: Opportunity) -> _Evidence:
    """Run the local rules; keep only requirement text + status (evidence stays here)."""
    criteria = check_criteria(profile, opportunity)
    return _Evidence(
        opportunity=opportunity,
        record_text=_record_text(opportunity),
        verdict_lines=_verdict_lines(criteria),
        assessment=assess_eligibility(criteria, opportunity),
        unknown=tuple(c.text for c in criteria if c.status is CriteriaStatus.UNKNOWN),
    )


def _record_text(opp: Opportunity) -> str:
    """The public record as labelled lines; a missing field says `none stated`."""
    lines = [
        f"Title: {_clip(opp.title, 300)}",
        f"Organizer: {_clip(opp.organizer, 300)}",
        f"Type: {opp.type.value}",
        f"Mode: {opp.mode or _NONE}",
        f"Location: {_place(opp) or _NONE}",
        f"Language of the listing: {opp.language or _NONE}",
        f"Deadline: {_deadline_line(opp)}",
    ]
    if opp.is_expired:
        lines.append("Status: the deadline has already passed")
    lines.append(f"Funding: {_clip(opp.funding or '', MAX_FIELD_CHARS) or _NONE}")
    lines += _bullets("Eligibility requirements", opp.eligibility)
    lines += _bullets("Benefits", opp.benefits)
    lines += [
        f"Summary: {_clip(opp.summary, MAX_FIELD_CHARS) or _NONE}",
        f"URL: {opp.url or _NONE}",
        f"Source: {opp.source}",
        f"Trust level: {opp.trust_level.value}",
        f"Scam warnings: {_scam_line(opp)}",
    ]
    if opp.review_notes:
        lines += _bullets("To verify", opp.review_notes)
    return "\n".join(lines)


def _verdict_lines(criteria: list[EligibilityCriterion]) -> str:
    """One `MET` / `NOT MET` / `UNKNOWN` line per requirement — never the evidence."""
    labels = {
        CriteriaStatus.MET: "MET",
        CriteriaStatus.MISSED: "NOT MET",
        CriteriaStatus.UNKNOWN: "UNKNOWN",
    }
    if not criteria:
        return "The source states no requirements."
    shown = criteria[:MAX_LIST_ITEMS]
    return "\n".join(f"- {labels[c.status]}: {_clip(c.text, MAX_LINE_CHARS)}" for c in shown)


def _deadline_line(opp: Opportunity) -> str:
    if opp.deadline is None:
        return _NONE
    return f"{opp.deadline.isoformat()} (stated in the source)"


def _place(opp: Opportunity) -> str:
    return ", ".join(part for part in (opp.location.strip(), opp.country.strip()) if part)


def _scam_line(opp: Opportunity) -> str:
    if not opp.scam_flags:
        return "none flagged"
    return "; ".join(
        f"{flag.flag.value}" + (f" ({_clip(flag.detail, 120)})" if flag.detail else "")
        for flag in opp.scam_flags[:5]
    )


def _bullets(label: str, items: list[str]) -> list[str]:
    clean = [_clip(item, MAX_LINE_CHARS) for item in items if item and item.strip()]
    clean = clean[:MAX_LIST_ITEMS]
    if not clean:
        return [f"{label}: {_NONE}"]
    return [f"{label}:", *(f"- {item}" for item in clean)]


def _clip(text: str, limit: int) -> str:
    """Collapse whitespace and cut to `limit` characters."""
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# Prompt + model call
# --------------------------------------------------------------------------- #
def _prompt(
    evidence: _Evidence, turns: list[ChatTurn], question: str, hint: str, budget: int
) -> str:
    """The user prompt; the oldest turns are dropped first until it fits `budget` chars."""
    kept = list(turns)
    while True:
        text = _render(evidence, kept, question, hint)
        if len(text) <= budget or not kept:
            return text
        kept = kept[1:]


def _render(evidence: _Evidence, turns: list[ChatTurn], question: str, hint: str) -> str:
    """Sections in the order the system prompt promises; the question comes first."""
    parts = [
        f"Reply language hint: {hint}",
        f"Question: {_clip(question, MAX_QUESTION_CHARS)}",
        "",
        "Opportunity record:",
        evidence.record_text,
        "",
        "Requirement check (computed locally; abstract outcomes only):",
        evidence.verdict_lines,
    ]
    if turns:
        parts += ["", "Recent conversation (oldest first):"]
        parts += [f"{turn.role}: {_clip(turn.content, MAX_TURN_CHARS)}" for turn in turns]
    return "\n".join(parts)


def _recent_turns(history: list[ChatTurn], question: str, limit: int) -> list[ChatTurn]:
    """The last `limit` turns, without the current question if a UI already stored it."""
    turns = list(history)
    if turns and turns[-1].role == "user" and " ".join(turns[-1].content.split()) == question:
        turns = turns[:-1]
    return turns[-limit:] if limit > 0 else []


def _model_reply(
    evidence: _Evidence,
    history: list[ChatTurn],
    question: str,
    hint: str,
    settings: Settings,
) -> tuple[ChatAnswer | None, str]:
    """One cached structured call behind the gate; (None, why) when there is no model answer."""
    if not model_allowed(settings):
        return None, _WHY_OFF
    system = (settings.prompts_dir / PROMPT_FILE).read_text(encoding="utf-8")
    turns = _recent_turns(history, question, settings.chat_history_turns)
    prompt = _prompt(evidence, turns, question, hint, settings.llm_max_input_chars)
    try:
        return get_llm(settings.llm_provider).structured(prompt, ChatAnswer, system=system), ""
    except QuotaExhausted as exc:  # never retried: a retry cannot help and burns the quota
        logger.warning("chat: quota exhausted, rules-only answer (%s)", _brief(exc))
        return None, _WHY_QUOTA
    except Exception as exc:  # LLMError, SDK errors, bad JSON: a chat must never crash
        logger.warning("chat: model failed, rules-only answer (%s)", _brief(exc))
        return None, _WHY_ERROR


def _brief(exc: Exception) -> str:
    """A provider error trimmed to one short log line."""
    text = " ".join(str(exc).split())
    return text if len(text) <= 120 else text[:117] + "..."


# --------------------------------------------------------------------------- #
# Links and pasted announcements -> extracted_opportunity
# --------------------------------------------------------------------------- #
def _first_url(text: str) -> str:
    match = _URL_RE.search(text)
    return match.group(0).rstrip(".,;:!?") if match else ""


def _read_attachment(message: str, settings: Settings) -> tuple[Opportunity | None, list[str]]:
    """Extract the opportunity a message carries (link or long pasted text), if any.

    The raw message is used (line breaks intact): the rule-first deadline lines of
    the extractor are line-based.
    """
    url = _first_url(message)
    if not url and len(message) < PASTE_MIN_CHARS:
        return None, []
    label = "Link" if url else "Pasted text"
    if not model_allowed(settings):
        return None, [f"{label} not used: model calls are off."]
    try:
        if url:
            found = extract_opportunity(url=url, source_name="chat", settings=settings)
        else:
            found = extract_opportunity(text=message, source_name="chat", settings=settings)
    except ApiError as exc:
        reason = _ATTACHMENT_NOTES.get(exc.code, "it could not be analysed")
        return None, [f"{label} not used: {reason}."]
    except Exception as exc:  # extraction must never take the chat down
        logger.warning("chat: extraction failed (%s)", _brief(exc))
        return None, [f"{label} not used: it could not be analysed."]
    return found, []


# --------------------------------------------------------------------------- #
# Post-processing: the contract is enforced here, not trusted from the model
# --------------------------------------------------------------------------- #
def _finalize(
    reply: ChatAnswer,
    evidence: _Evidence,
    hint: str,
    extracted: Opportunity | None,
    notes: list[str],
) -> ChatAnswer:
    """Enforce refusal + grounding, attach the local eligibility, validate via ChatAnswer."""
    text = reply.answer.strip()
    in_source = bool(text) and reply.in_source and REFUSAL_PHRASE not in text.casefold()
    if not in_source and REFUSAL_PHRASE not in text.casefold():
        text = f"{text} That is {REFUSAL_PHRASE}.".strip()
    if notes:
        text = "\n".join([text, *(f"Note: {note}" for note in notes)])
    return ChatAnswer(
        answer=text,
        language=_language(reply.language, hint),
        citations=_clean_citations(reply.citations, evidence),
        in_source=in_source,
        eligibility=evidence.assessment,
        extracted_opportunity=extracted,
    )


def _clean_citations(citations: list[Citation], evidence: _Evidence) -> list[Citation]:
    """Keep only quotes that really appear in the record; url/title always the record's."""
    opp = evidence.opportunity
    corpus = _squash(evidence.record_text)
    kept: list[Citation] = []
    for citation in citations:
        quote = " ".join(citation.quote.split())
        if quote and _squash(quote) not in corpus:
            continue  # a quote the record does not contain is an invented one
        if all(quote != existing.quote for existing in kept):
            kept.append(Citation(url=opp.url, title=opp.title, quote=quote))
    return kept[:3] or [Citation(url=opp.url, title=opp.title)]


def _squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def _language(value: str, hint: str) -> str:
    """The model's language code when it is a code, else the offline hint."""
    code = (value or "").strip().lower()
    return code if _LANGUAGE_RE.match(code) else hint


def _no_source(notes: list[str]) -> ChatAnswer:
    """No opportunity at all: nothing to ground an answer in."""
    text = (
        f"I have no opportunity record to answer from, so that is {REFUSAL_PHRASE}. "
        "Select an opportunity, or paste its announcement or a link."
    )
    if notes:
        text = "\n".join([text, *(f"Note: {note}" for note in notes)])
    return ChatAnswer(answer=text, in_source=False)


# --------------------------------------------------------------------------- #
# Rules-only fallback (gate closed, 429 or model failure)
# --------------------------------------------------------------------------- #
def _rules_text(evidence: _Evidence, why: str) -> str:
    """Deadline, funding and requirement verdicts straight from the record + local rules."""
    opp = evidence.opportunity
    parts = [why, _deadline_sentence(opp)]
    if opp.funding:
        parts.append(f"Funding: {_clip(opp.funding, 200)}.")
    assessment = evidence.assessment
    if assessment.met:
        parts.append("Requirements you meet: " + "; ".join(assessment.met) + ".")
    if assessment.gaps:
        parts.append("Requirements you do not meet yet: " + "; ".join(assessment.gaps) + ".")
    if evidence.unknown:
        parts.append("Requirements to check yourself: " + "; ".join(evidence.unknown) + ".")
    return " ".join(parts)


def _deadline_sentence(opp: Opportunity) -> str:
    if opp.deadline is None:
        return "No deadline is stated in the record."
    return f"Deadline: {opp.deadline.isoformat()} (as stated in the source)."
