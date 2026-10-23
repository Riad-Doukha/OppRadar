# matching/ package: profile x opportunity scoring (hard filters, criteria rules,
# embedding similarity, 0-100 score with reasons) and the notification rules.
# Everything here is deterministic and offline; the LLM may only reword reasons.

from oppradar_ai.matching.composer import score_user
from oppradar_ai.matching.criteria import (
    check_criteria,
    evaluate_line,
    experience_years,
    normalize_language,
    profile_blob,
)
from oppradar_ai.matching.filters import apply_hard_filters, drop_reason
from oppradar_ai.matching.notifications import (
    decide_notifications,
    in_quiet_hours,
    prefs_from_settings,
)
from oppradar_ai.matching.reasons import phrase_reasons, phrasing_allowed, rule_reasons
from oppradar_ai.matching.score import combine, compute_bonus, criteria_ratio
from oppradar_ai.matching.texts import opportunity_text, profile_text

__all__ = [
    "apply_hard_filters",
    "check_criteria",
    "combine",
    "compute_bonus",
    "criteria_ratio",
    "decide_notifications",
    "drop_reason",
    "evaluate_line",
    "experience_years",
    "in_quiet_hours",
    "normalize_language",
    "opportunity_text",
    "phrase_reasons",
    "phrasing_allowed",
    "prefs_from_settings",
    "profile_blob",
    "profile_text",
    "rule_reasons",
    "score_user",
]
