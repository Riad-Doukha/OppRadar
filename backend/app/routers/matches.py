"""Match endpoints — scored opportunities for a profile."""

from fastapi import APIRouter

router = APIRouter()

# TODO(Riad): GET /matches?profile_id=... reads MatchResult rows;
# POST /matches/recompute loads the profile and calls
# `oppradar_ai.matching.score_matches(profile, opportunities)`.
