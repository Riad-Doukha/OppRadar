# Extractor tests: cheap rules run offline, LLM (fake provider) fills the
# schema, regex backfills anything the LLM left empty.

from pathlib import Path

from oppradar_ai.documents.extractors import (
    extract_certificate,
    extract_cv,
    extract_portfolio,
    find_emails,
    find_phones,
    find_urls,
)
from oppradar_ai.documents.reader import read_document
from oppradar_ai.schemas import CertificateExtraction, CVExtraction, PortfolioExtraction

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def test_find_emails_dedupes() -> None:
    assert find_emails("a@b.com, a@b.com, name+tag@x.org") == ["a@b.com", "name+tag@x.org"]


def test_find_urls_strips_trailing_punctuation() -> None:
    assert find_urls("see https://example.org/page, then stop") == ["https://example.org/page"]


def test_find_phones_detects_number() -> None:
    phones = find_phones("call +213 555 000 111 today")
    assert phones and phones[0].startswith("+213")


def test_find_phones_ignores_year_ranges() -> None:
    # a CV education line must not be read as a phone number
    assert find_phones("BSc Web Development, ENSMAD Oran, 2021 - 2024") == []


def test_extract_cv_schema_and_rules_backfill(caplog) -> None:
    doc = read_document(SAMPLES / "cv_amine.pdf")
    with caplog.at_level("INFO", logger="oppradar_ai.documents.extractors"):
        cv = extract_cv(doc.text, doc.file_name)
    assert isinstance(cv, CVExtraction)
    assert cv.email == "amine.kaddour@example.org"  # regex, even with the fake LLM
    # the backfill announces itself so notebooks/UIs can show what the rules did
    assert any(
        r.message.startswith("regex backfill filled") and r.message.endswith("cv_amine.pdf")
        for r in caplog.records
    )
    assert cv.source_file == "cv_amine.pdf"
    assert cv.skills  # canned fake data
    assert any("example-user" in url for url in cv.links)


def test_extract_cv_deterministic() -> None:
    doc = read_document(SAMPLES / "cv_amine.docx")
    first = extract_cv(doc.text, doc.file_name)
    second = extract_cv(doc.text, doc.file_name)
    assert first.model_dump() == second.model_dump()


def test_extract_certificate_backfills_credential_url() -> None:
    doc = read_document(SAMPLES / "certificate_alx_amine.pdf")
    ext = extract_certificate(doc.text, doc.file_name)
    assert isinstance(ext, CertificateExtraction)
    assert ext.credential_url == "https://credentials.alx.example/amine-dl-2025"
    assert ext.source_file == "certificate_alx_amine.pdf"


def test_extract_portfolio_backfills_email_and_links() -> None:
    doc = read_document(SAMPLES / "portfolio_sara.docx")
    ext = extract_portfolio(doc.text, doc.file_name)
    assert isinstance(ext, PortfolioExtraction)
    assert ext.email == "sara.belkacem@example.org"
    assert any("github.com/sarab" in url for url in ext.links)
