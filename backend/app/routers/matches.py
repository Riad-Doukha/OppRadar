"""Match endpoints — scored opportunities for the signed-in user.

Waiting on the AI matching phase. When it ships: POST /matches/recompute builds
`services.ai.to_ai_profile(me)`, calls the matcher through services/ai.py,
stores rows in public.matches and emits `match:update`; GET /matches reads them.
"""

from fastapi import APIRouter

router = APIRouter()
