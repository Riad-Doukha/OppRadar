"""Turn raw fetched records into validated Opportunity objects.

Fast path first (JSON sources that already look structured), LLM second.
Every record that reaches the LLM costs exactly one call, so de-duplication
happens *before* extraction where possible and retries are capped.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from oppradar_ai import llm
from oppradar_ai.errors import ExtractionError
from oppradar_ai.schemas import Mode, Opportunity, OpportunityType

logger = logging.getLogger(__name__)

TYPE_KEYWORDS: dict[OpportunityType, tuple[str, ...]] = {
    OpportunityType.INTERNSHIP: ("internship", "intern", "stagiaire", "trainee"),
    OpportunityType.JOB: ("job", "hiring", "full-time", "part-time", "emploi", "remote role"),
    OpportunityType.SCHOLARSHIP: ("scholarship", "bourse", "grant", "fellowship", "funding"),
    OpportunityType.COMPETITION: ("competition", "contest", "hackathon", "challenge", "prize"),
    OpportunityType.BOOTCAMP: ("bootcamp", "academy", "training", "program", "course"),
    OpportunityType.RESEARCH: ("research", "phd", "thesis", "lab", "assistantship"),
    OpportunityType.VOLUNTEER: ("volunteer", "volunteering", "beneficiary"),
}

MODE_KEYWORDS: dict[Mode, tuple[str, ...]] = {
    Mode.REMOTE: ("remote", "à distance", "work from home"),
    Mode.HYBRID: ("hybrid", "flexible"),
    Mode.ONSITE: ("on-site", "onsite", "in-office", "presentiel", "on site"),
}

PROMPT = """You convert a raw web record into a structured opportunity.

Return ONLY a JSON object with these keys:
  title (string), organization (string),
  type (one of: internship, job, scholarship, competition, bootcamp, research, volunteer),
  mode (one of: remote, hybrid, onsite, or null if unknown),
  location (string or null), country (string or null),
  deadline (YYYY-MM-DD string or null),
  salary (string or null), description (string, max 600 chars),
  tags (array of lowercase strings, max 8).

Rules:
- Never invent information that is not in the record.
- organization may be inferred from the record's sender/domain, else use "Unknown".
- deadline null when no explicit closing date is stated.

Raw record:
---
{record}
---
"""


# --------------------------------------------------------------------------- #
# Fast path — no LLM
# --------------------------------------------------------------------------- #
def _from_structured(raw: dict[str, Any]) -> Opportunity | None:
    """Handle already-structured JSON items (Remotive/RemoteOK style)."""
    data = raw.get("raw") if isinstance(raw.get("raw"), dict) else {}
    title = (data.get("title") or raw.get("title") or "").strip()
    if not title or not raw.get("url"):
        return None

    opp_type = OpportunityType.JOB
    for candidate, keywords in TYPE_KEYWORDS.items():
        haystack = f"{title} {data.get('tags', '')}".lower()
        if any(k in haystack for k in keywords):
            opp_type = candidate
            break

    mode = None
    category = str(data.get("category") or "").lower()
    for candidate, keywords in MODE_KEYWORDS.items():
        if any(k in category or k in title.lower() for k in keywords):
            mode = candidate
            break
    if mode is None and data.get("remote") is True:
        mode = Mode.REMOTE

    deadline = None
    if data.get("deadline"):
        try:
            deadline = date.fromisoformat(str(data["deadline"])[:10])
        except ValueError:
            pass

    return Opportunity(
        title=title[:200],
        organization=str(data.get("company_name") or data.get("company") or "Unknown"),
        type=opp_type,
        mode=mode,
        location=data.get("location"),
        deadline=deadline,
        salary=data.get("salary"),
        description=str(data.get("description") or raw.get("description") or "")[:600],
        tags=[str(t).lower() for t in (data.get("tags") or [])][:8],
        source=raw.get("source", "unknown"),
        source_url=raw["url"],
    )


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #
def extract_one(raw: dict[str, Any]) -> Opportunity | None:
    """Extract one raw record. Returns None when it isn't an opportunity."""
    if not raw.get("url") or not (raw.get("title") or raw.get("description")):
        return None

    fast = _from_structured(raw)
    if fast is not None:
        return fast

    if not llm.is_configured():
        raise ExtractionError("LLM_API_KEY not set and record is not structured enough for the fast path")

    prompt = PROMPT.format(record=json.dumps(raw, ensure_ascii=False, default=str)[:4000])
    try:
        data = llm.chat_json([{"role": "user", "content": prompt}])
    except Exception as exc:
        logger.warning("extraction failed for %s: %s", raw.get("url"), exc)
        return None

    if not data.get("title"):
        return None  # not an opportunity after all
    data.setdefault("type", "job")

    try:
        if data.get("deadline"):
            data["deadline"] = date.fromisoformat(str(data["deadline"])[:10])
        if data.get("fetched_at") and isinstance(data["fetched_at"], str):
            data["fetched_at"] = datetime.fromisoformat(data["fetched_at"])
        data["source"] = raw.get("source", "unknown")
        data["source_url"] = raw["url"]
        return Opportunity.model_validate(data)
    except Exception as exc:
        logger.warning("invalid extraction for %s: %s", raw.get("url"), exc)
        return None


def extract_batch(raw_records: list[dict[str, Any]]) -> list[Opportunity]:
    """Extract a whole batch; one bad record never kills the run."""
    results: list[Opportunity] = []
    seen_urls: set[str] = set()
    for raw in raw_records:
        url = str(raw.get("url", "")).strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            opp = extract_one(raw)
        except ExtractionError:
            raise  # configuration problems should surface immediately
        except Exception as exc:
            logger.warning("unexpected extraction error for %s: %s", url, exc)
            continue
        if opp is not None:
            results.append(opp)
    return results
