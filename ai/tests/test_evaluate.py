# Grader tests: case-insensitive + whitespace-normalized comparison, item and
# set matching, and a round-trip against the real ground-truth files.

import json
from pathlib import Path

from oppradar_ai.documents.evaluate import grade_extraction, normalize
from oppradar_ai.schemas import CVExtraction, EducationItem

TRUTH = Path(__file__).resolve().parents[1] / "data" / "samples" / "ground_truth"


def test_normalize_case_and_whitespace() -> None:
    assert normalize("  MSc   Data\tScience ") == "msc data science"
    assert normalize(None) == ""


def test_scalar_match_is_case_insensitive() -> None:
    grade = grade_extraction(
        "cv", CVExtraction(full_name="AMINE  KADDOUR"), {"full_name": "Amine Kaddour"}
    )
    assert grade.accuracy == 1.0
    assert grade.per_field["full_name"] is True


def test_wrong_value_is_reported_as_missing() -> None:
    grade = grade_extraction("cv", CVExtraction(email="x@y.com"), {"email": "a@b.com"})
    assert grade.accuracy == 0.0
    assert grade.missing == ["email: a@b.com"]


def test_skill_sets_compare_as_sets() -> None:
    cv = CVExtraction(skills=["Python ", "PYTORCH"])
    grade = grade_extraction("cv", cv, {"skills": ["python", "pytorch"]})
    assert grade.per_field["skills"] is True
    assert grade.missing == []

    partial = grade_extraction(
        "cv", CVExtraction(skills=["python"]), {"skills": ["python", "pytorch"]}
    )
    assert partial.per_field["skills"] is False
    assert any("pytorch" in m for m in partial.missing)


def test_items_match_on_normalized_subfields() -> None:
    cv = CVExtraction(education=[EducationItem(institution="ENSICAEN", degree=" MSc ")])
    grade = grade_extraction(
        "cv", cv, {"education": [{"institution": "ensicaen", "degree": "msc"}]}
    )
    assert grade.per_field["education"] is True

    mismatch = grade_extraction("cv", cv, {"education": [{"institution": "DAAD", "degree": "msc"}]})
    assert mismatch.per_field["education"] is False
    assert mismatch.missing
    assert "got" in mismatch.missing[0]  # shows the extracted side, not just the expected


def test_empty_expectations_are_not_graded() -> None:
    grade = grade_extraction("cv", CVExtraction(), {"skills": [], "email": None})
    assert grade.fields_checked == 0
    assert grade.accuracy == 1.0


def test_ground_truth_round_trip_is_perfect() -> None:
    truth = json.loads((TRUTH / "cv_amine.json").read_text(encoding="utf-8"))
    cv = CVExtraction.model_validate(
        {k: v for k, v in truth.items() if k in CVExtraction.model_fields}
    )
    grade = grade_extraction("cv_amine.json", cv, truth)
    assert grade.accuracy == 1.0
    assert grade.missing == []
