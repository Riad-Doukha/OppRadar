"""Chat endpoints — the retrieval-augmented assistant."""

from fastapi import APIRouter

router = APIRouter()

# TODO(Riad): POST /chat/ask accepts {question, history?, profile_id?} and
# returns `oppradar_ai.chat.ask(question, history, profile)`.
