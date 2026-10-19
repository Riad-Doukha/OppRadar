"""Matching: hard filters → soft score → reasons.

    from oppradar_ai.matching import score_matches
    matches = score_matches(profile, opportunities, top_k=20)
"""

from oppradar_ai.matching.filters import hard_filters
from oppradar_ai.matching.reasons import build_reasons
from oppradar_ai.matching.scorer import score_matches

__all__ = ["score_matches", "hard_filters", "build_reasons"]
