"""Chat endpoints — the grounded assistant.

Waiting on the AI chat phase. When it ships: POST /chat takes {question} and
returns a `ChatAnswer` (answer, citations, eligibility) via services/ai.py,
persisting both turns in public.chat_messages; GET /chat/history lists them.
"""

from fastapi import APIRouter

router = APIRouter()
