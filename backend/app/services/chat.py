"""Ask the agent — the chat behind /agent.

The conversational AI agent isn't shipped yet (AI chat phase). Until it is,
answers are honest look-ups in OppRadar's own data:
  - a pasted link that matches an opportunity -> that opportunity's card
  - words -> opportunities matching any of the keywords
and every answer says what the full agent will add. When the AI phase lands,
`answer()` calls services/ai.py instead and stores its citations/eligibility.

History is stored only with the `chat_history` consent (Settings → Privacy & AI).
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from oppradar_ai.schemas import ChatTurn

from app.auth import CurrentUser
from app.models import ChatHistory, ChatMessageOut, OpportunityFilters, OpportunityOut
from app.repositories import Repository
from app.repositories.base import Row
from app.services import ai, profiles

HISTORY_LIMIT = 100
MAX_CARDS = 3
URL_RE = re.compile(r"https?://\S+|\b[\w-]+(?:\.[\w-]+)+/\S*", re.IGNORECASE)
# Small EN/FR stop-word list so "what documents do I need for X" searches for X.
_STOP_WORDS = """
    a an and are can do does for from how i in is it me my need of on or show the this to what
    when where which who why with you your about any am be will would le la les de des du un une
    et pour quel quelle quels est ce que qui dans sur avec mon ma mes
"""
STOP = frozenset(_STOP_WORDS.split())
# Words that name an opportunity type (EN/FR, singular/plural). The search
# index covers title/organizer/summary/location only, so "hackathons" must
# become a type filter rather than a keyword.
TYPE_WORDS: dict[str, str] = {
    **dict.fromkeys(["hackathon", "hackathons"], "hackathon"),
    **dict.fromkeys(["datathon", "datathons"], "datathon"),
    **dict.fromkeys(["internship", "internships", "intern", "stage", "stages"], "internship"),
    **dict.fromkeys(["scholarship", "scholarships", "bourse", "bourses"], "scholarship"),
    **dict.fromkeys(["competition", "competitions", "contest", "concours"], "competition"),
    **dict.fromkeys(["job", "jobs", "emploi"], "job"),
    **dict.fromkeys(["fellowship", "fellowships"], "fellowship"),
    **dict.fromkeys(["bootcamp", "bootcamps"], "bootcamp"),
    **dict.fromkeys(["volunteer", "volunteering", "bénévolat"], "volunteer"),
    **dict.fromkeys(["grant", "grants"], "grant"),
    **dict.fromkeys(["course", "courses", "formation"], "course"),
    **dict.fromkeys(["research"], "research"),
}
NOT_YET = (
    "Open an opportunity and ask from its page for an answer grounded in its official text, "
    "with your eligibility."
)


log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _keeps_history(repo: Repository, user: CurrentUser) -> bool:
    return not user.is_demo and "chat_history" in repo.active_consents(user.id)


def _cards(repo: Repository, ids: list[str]) -> list[OpportunityOut]:
    if not ids:
        return []
    rows, _ = repo.list_opportunities(OpportunityFilters(ids=ids, include_expired=True, limit=10))
    by_id = {str(r["id"]): r for r in rows}
    return [OpportunityOut.model_validate(by_id[i]) for i in ids if i in by_id]


def _out(repo: Repository, row: Row) -> ChatMessageOut:
    ids = [str(i) for i in row.get("opportunity_ids") or []]
    return ChatMessageOut.model_validate({**row, "opportunities": _cards(repo, ids)})


def history(repo: Repository, user: CurrentUser) -> ChatHistory:
    saved = _keeps_history(repo, user)
    rows = repo.list_chat(user.id, HISTORY_LIMIT) if saved else []
    return ChatHistory(messages=[_out(repo, r) for r in rows], saved=saved)


def answer(repo: Repository, message: str) -> tuple[str, list[str], list[dict]]:
    """(text, opportunity ids, citations) for one question, without the AI."""
    link = URL_RE.search(message)
    if link:
        url = link.group(0).rstrip(").,;")
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").removeprefix("www.")
        path = parsed.path.rstrip("/")
        rows, _ = repo.list_opportunities(
            OpportunityFilters(url_like=f"{host}{path}", include_expired=True, limit=MAX_CARDS)
        )
        if not rows and host:
            rows, _ = repo.list_opportunities(
                OpportunityFilters(url_like=host, include_expired=True, limit=MAX_CARDS)
            )
        if rows:
            text = (
                f"I found {'this opportunity' if len(rows) == 1 else 'these opportunities'} from "
                f"{host} in OppRadar. The requirements are on the opportunity page — compare them "
                f"with your profile. {NOT_YET}"
            )
            return text, [str(r["id"]) for r in rows], _citations(rows)
        return (
            f"I can't read {host or 'that page'} yet, and it isn't in OppRadar's sources. "
            f"Open it and compare its requirements with your profile. {NOT_YET}",
            [],
            [],
        )

    words = [w for w in re.findall(r"[\w'-]+", message.lower()) if len(w) > 2 and w not in STOP]
    if not words:
        return (
            "Tell me what you're looking for — a type (internship, hackathon, scholarship…), "
            f"a field or an organisation. {NOT_YET}",
            [],
            [],
        )
    types = list(dict.fromkeys(TYPE_WORDS[w] for w in words if w in TYPE_WORDS))
    terms = [w for w in words if w not in TYPE_WORDS][:8]
    keywords = " ".join(words[:8])
    rows, total = repo.list_opportunities(
        OpportunityFilters(q=" ".join(terms) or None, match_any=True, types=types, limit=MAX_CARDS)
    )
    if not rows and types and terms:  # the words narrowed too much: try the type alone
        rows, total = repo.list_opportunities(OpportunityFilters(types=types, limit=MAX_CARDS))
    if not rows:
        return (
            f"I didn't find open opportunities matching “{keywords}”. Try a type "
            f"(internship, hackathon, scholarship…) or a field. {NOT_YET}",
            [],
            [],
        )
    more = f" Showing {len(rows)} of {total}." if total > len(rows) else ""
    text = f"Here's what I found in OppRadar for “{keywords}”.{more} {NOT_YET}"
    return text, [str(r["id"]) for r in rows], _citations(rows)


def _citations(rows: list[Row]) -> list[dict]:
    return [{"url": r.get("url") or "", "title": r["title"], "quote": ""} for r in rows]


AI_ANSWERS_PER_DAY = 20  # free-tier budget per user; then answers fall back to search
_ai_used: dict[str, tuple[date, int]] = {}
_ai_lock = threading.Lock()


def _ai_budget_left(user_id: str) -> bool:
    """Count one AI answer for today; False once the daily limit is reached."""
    today = date.today()
    with _ai_lock:
        day, used = _ai_used.get(user_id, (today, 0))
        used = used if day == today else 0
        if used >= AI_ANSWERS_PER_DAY:
            return False
        _ai_used[user_id] = (today, used + 1)
        return True


def _ai_reply(
    repo: Repository, user: CurrentUser, message: str, opportunity_id: str | None, ids: list[str]
) -> dict[str, Any] | None:
    """Grounded AI answer, or None when the AI chat is unavailable (keyword reply stays)."""
    if opportunity_id is None and URL_RE.search(message) and ids:
        opportunity_id = ids[0]  # a pasted link resolved to an opportunity we know
    row = repo.get_opportunity(opportunity_id) if opportunity_id else None
    if row is None:
        # The AI answers about one opportunity; open questions stay a search.
        return None
    if not _ai_budget_left(user.id):
        log.info("daily AI answer limit reached for %s; search answer used", user.id)
        return None
    try:
        me = profiles.load_me(repo, user)
        past = repo.list_chat(user.id, 10) if _keeps_history(repo, user) else []
        turns = [ChatTurn(role=t["role"], content=t["content"]) for t in past]
        reply = ai.answer(ai.to_ai_profile(me), ai.opportunity_from_row(row), turns, message)
    except Exception as exc:  # ApiError (chat-unavailable, offline…) / LLMError
        log.info("AI chat unavailable, keyword answer used: %s", exc)
        return None
    return {
        "content": reply.answer,
        "citations": [c.model_dump(mode="json") for c in reply.citations],
        "in_source": reply.in_source,
        "eligibility": reply.eligibility.model_dump(mode="json") if reply.eligibility else None,
        "opportunity_ids": [str(row["id"])],
    }


EXTRACT_MIN_CHARS = 300  # a pasted announcement (no link) long enough to read


def _extract(user: CurrentUser, message: str, ids: list[str]) -> dict[str, Any] | None:
    """A link we don't know, or a pasted announcement: let the AI read it so the
    user can send it for review. None when nothing usable came out."""
    link = URL_RE.search(message)
    if ids or (not link and len(message) < EXTRACT_MIN_CHARS) or not _ai_budget_left(user.id):
        return None
    try:
        if link:
            url = link.group(0).rstrip(").,;")
            opp = ai.extract_opportunity(url=url if "://" in url else f"https://{url}")
        else:
            opp = ai.extract_opportunity(text=message)
    except Exception as exc:  # gate closed (offline), unreadable page, not an opportunity…
        log.info("extraction skipped: %s", exc)
        return None
    row = ai.opportunity_row(opp)
    keep = ("title", "organizer", "type", "mode", "location", "country", "language", "deadline",
            "funding", "eligibility", "benefits", "summary", "url")  # fmt: skip
    return {k: row.get(k) for k in keep}


def ask(
    repo: Repository, user: CurrentUser, message: str, opportunity_id: str | None = None
) -> ChatHistory:
    """Answer one message; returns just the new turn (user + assistant)."""
    saved = _keeps_history(repo, user)
    text, ids, citations = answer(repo, message.strip())
    reply = _ai_reply(repo, user, message.strip(), opportunity_id, ids)
    extracted = None if reply else _extract(user, message.strip(), ids)
    if extracted:
        text = (
            f"I read “{extracted['title']}” by {extracted['organizer']}. "
            "It isn't in OppRadar yet — check the details below and send it for review "
            "if it's worth sharing."
        )
    turns: list[ChatMessageOut] = []
    for row in (
        {"user_id": user.id, "role": "user", "content": message.strip()},
        {
            "user_id": user.id,
            "role": "assistant",
            **(
                reply
                or {
                    "content": text,
                    "citations": citations,
                    "opportunity_ids": ids,
                    "extracted": extracted,
                }
            ),
        },
    ):
        stored = repo.add_chat(row) if saved else {**row, "id": None, "created_at": _now()}
        turns.append(_out(repo, stored))
    return ChatHistory(messages=turns, saved=saved, ai_available=reply is not None)


def clear(repo: Repository, user: CurrentUser) -> None:
    repo.clear_chat(user.id)
