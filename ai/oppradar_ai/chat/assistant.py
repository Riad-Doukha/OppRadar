"""The assistant — retrieval-augmented answers about opportunities.

Contract (interface #5 in docs/ai-interface.md):
- grounded in retrieved opportunities only — never invents postings,
- cites the URLs it actually used,
- raises LLMError immediately when no key is configured.
"""

from __future__ import annotations

from oppradar_ai import llm
from oppradar_ai.chat.prompts import SYSTEM_PROMPT, build_user_prompt
from oppradar_ai.chat.retrieval import DEFAULT_K, OpportunityIndex
from oppradar_ai.errors import LLMError
from oppradar_ai.schemas import ChatMessage, ChatResponse, Profile

# The index the assistant answers from — the backend swaps this at startup
# (or after each ingestion run). Module-level keeps the call simple.
_index: OpportunityIndex | None = None


def set_index(index: OpportunityIndex | None) -> None:
    global _index
    _index = index


def get_index() -> OpportunityIndex | None:
    return _index


def ask(
    question: str,
    history: list[ChatMessage] | None = None,
    profile: Profile | None = None,
    *,
    index: OpportunityIndex | None = None,
    k: int = DEFAULT_K,
) -> ChatResponse:
    """Answer a question about the indexed opportunities."""
    if not llm.is_configured():
        raise LLMError("LLM_API_KEY is not set — the assistant cannot answer")

    index = index or _index
    question = question.strip()
    if not question:
        return ChatResponse(answer="Ask me something about the opportunities.", sources=[])

    hits = index.search(question, k=k, profile=profile) if index else []
    sources = [opp for opp, _score in hits]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in (history or [])[-6:]:  # keep the last few turns only
        messages.append({"role": msg.role.value, "content": msg.content})
    messages.append(
        {"role": "user", "content": build_user_prompt(question, sources, profile=profile)}
    )

    answer = llm.chat(messages, temperature=0.2, max_tokens=700)
    return ChatResponse(answer=answer, sources=sources)
