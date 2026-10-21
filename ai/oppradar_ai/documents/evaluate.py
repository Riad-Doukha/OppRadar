# Grades an extraction against data/samples/ground_truth/*.json. All string
# comparison is case-insensitive and whitespace-normalized ("  MSc   Data " ==
# "msc data"). Used by notebook 02 and the extraction tests.

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from oppradar_ai.schemas import ExtractionGrade

logger = logging.getLogger(__name__)


def normalize(value: Any) -> str:
    """Casefold and collapse whitespace so formatting never fails a comparison.

    Example:
        >>> normalize("  MSc   Data\\tScience ")
        'msc data science'
    """
    return " ".join(str(value if value is not None else "").casefold().split())


def grade_extraction(
    document: str, extraction: BaseModel, ground_truth: dict[str, Any]
) -> ExtractionGrade:
    """Score one extraction against its ground-truth dict (0..1 accuracy).

    Example:
        >>> from oppradar_ai.schemas import CVExtraction
        >>> g = grade_extraction("cv.pdf", CVExtraction(email="a@b.com"),
        ...                      {"email": "A@B.COM"})
        >>> g.accuracy, g.fields_checked
        (1.0, 1)
    """
    per_field: dict[str, bool] = {}
    missing: list[str] = []
    for key, expected in ground_truth.items():
        if expected in (None, "", [], {}):
            continue
        got = getattr(extraction, key, None)
        ok, missed = _grade_value(expected, got)
        per_field[key] = ok
        missing += [f"{key}: {m}" for m in missed]
    matched = sum(1 for ok in per_field.values() if ok)
    grade = ExtractionGrade(
        document=document,
        fields_checked=len(per_field),
        fields_matched=matched,
        accuracy=round(matched / len(per_field), 3) if per_field else 1.0,
        per_field=per_field,
        missing=missing,
    )
    logger.info(
        "graded %s: %.0f%% (%d/%d)", document, grade.accuracy * 100, matched, len(per_field)
    )
    return grade


def _grade_value(expected: Any, got: Any) -> tuple[bool, list[str]]:
    """Dispatch: list[str] -> set compare, list[dict] -> item compare, else scalar."""
    if isinstance(expected, list) and expected and isinstance(expected[0], dict):
        return _grade_items(expected, got or [])
    if isinstance(expected, list):
        return _grade_str_list([str(v) for v in expected], [str(v) for v in (got or [])])
    matched = normalize(expected) == normalize(got)
    return matched, [] if matched else [str(expected)]


def _grade_str_list(expected: list[str], got: list[str]) -> tuple[bool, list[str]]:
    """Set equality on normalized strings; returns the expected values missing."""
    want = {normalize(v) for v in expected if normalize(v)}
    have = {normalize(v) for v in got}
    missing = sorted(v for v in want if v not in have)
    return not missing, missing


def _grade_items(expected: list[dict], got: list[BaseModel]) -> tuple[bool, list[str]]:
    """Each expected item must match SOME got item on all its provided subfields."""
    missing: list[str] = []
    for i, want in enumerate(expected):
        if not any(_item_matches(want, item) for item in got):
            missing.append(f"[{i}] " + ", ".join(f"{k}={v}" for k, v in want.items()))
    return not missing, missing


def _item_matches(want: dict[str, Any], item: BaseModel) -> bool:
    """True when every expected subfield matches the model attribute (normalized)."""
    for key, value in want.items():
        if value in (None, ""):
            continue
        if normalize(value) != normalize(getattr(item, key, None)):
            return False
    return True
