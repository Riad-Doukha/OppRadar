# Builder tests: list unions with case-insensitive dedupe, conflict and
# needs-review reporting, completeness scoring, error passthrough.

from oppradar_ai.documents.profile_builder import build_profile
from oppradar_ai.schemas import (
    CertificateExtraction,
    CVExtraction,
    PortfolioExtraction,
    ProfileBuildResult,
)


def _cv(**kwargs) -> CVExtraction:
    return CVExtraction.model_validate(kwargs)


def test_skills_union_dedupes_case_insensitively() -> None:
    res = build_profile(
        [
            _cv(full_name="A", skills=["Python", "pytorch"], languages=["French"]),
            _cv(skills=["python ", "sql"]),
        ]
    )
    assert [s.lower().strip() for s in res.profile.skills] == ["python", "pytorch", "sql"]
    assert res.profile.languages == ["French"]
    assert isinstance(res, ProfileBuildResult)


def test_conflicting_names_are_reported() -> None:
    first, second = _cv(full_name="Amine Kaddour"), _cv(full_name="Someone Else")
    res = build_profile([first, second])
    assert any(c.startswith("full_name:") for c in res.conflicts)
    assert res.profile.conflicts == res.conflicts
    assert any(
        c.field == "full_name" and c.confidence == 0.3 for c in res.profile.field_confidences
    )


def test_certificate_extraction_becomes_certificate() -> None:
    cert = CertificateExtraction(
        title="Deep Learning Bootcamp", issuer="ALX Africa", source_file="cert.pdf"
    )
    res = build_profile([_cv(full_name="Amine"), cert])
    assert len(res.profile.certificates) == 1
    assert res.profile.certificates[0].source_file == "cert.pdf"


def test_portfolio_projects_merge_with_cv_projects() -> None:
    port = PortfolioExtraction(
        full_name="Sara",
        projects=[{"name": "Logistics Tracker", "url": "https://github.com/sarab/logistics-tracker"}],
    )
    cv_project = _cv(full_name="Sara", projects=[{"name": "Other", "url": "https://x.org/o"}])
    res = build_profile([cv_project, port])
    assert len(res.profile.projects) == 2


def test_needs_review_becomes_low_confidence() -> None:
    res = build_profile([_cv(full_name="A", needs_review=["headline"])])
    assert any(
        f.field == "headline" and f.confidence == 0.5 and f.needs_review
        for f in res.profile.field_confidences
    )


def test_completeness_bounds_and_suggestions() -> None:
    empty = build_profile([_cv()])
    assert empty.completeness == 0.0
    assert len(empty.suggestions) == 10

    full = build_profile(
        [
            _cv(
                full_name="A",
                email="a@b.com",
                headline="Data student",
                country="Algeria",
                summary="Looking for internships.",
                skills=["python"],
                languages=["french"],
                education=[{"institution": "X", "degree": "MSc"}],
                experience=[{"organization": "Y", "title": "Intern"}],
                projects=[{"name": "Z", "url": "https://z.org"}],
            )
        ]
    )
    assert full.completeness == 1.0
    assert full.suggestions == []
    assert full.profile.completeness == full.completeness


def test_document_errors_pass_through() -> None:
    res = build_profile([_cv(full_name="A")], user_id="u-1", errors=["bad.pdf: unreadable"])
    assert res.document_errors == ["bad.pdf: unreadable"]
    assert res.profile.user_id == "u-1"
