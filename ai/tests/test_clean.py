# Cleaning tests: title/canonical/link extraction from the sample pages,
# readable main text, and no crash on garbage HTML.

from pathlib import Path

from oppradar_ai.ingestion.clean import clean_html

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def test_scholarship_page_cleans_to_readable_text() -> None:
    page = clean_html((SAMPLES / "page_scholarship.html").read_text(encoding="utf-8"), "local")
    assert page.title.startswith("Atlas Merit Scholarship 2027")
    assert page.canonical == "https://example.org/atlas-merit-scholarship-2027"
    assert "15 March 2027" in page.text  # deadline survives cleaning
    assert "monthly stipend" in page.text
    assert "dataLayer" not in page.text  # <script> junk removed
    assert "https://example.org/atlas-merit-scholarship-2027/apply" in page.links


def test_hackathon_page_uses_og_url_as_canonical() -> None:
    page = clean_html((SAMPLES / "page_hackathon.html").read_text(encoding="utf-8"), "local")
    assert page.canonical == "https://example.org/events/sahara-code-jam-2027"
    assert "2027-04-10" in page.text  # ISO deadline in the body
    assert "prize pool" in page.text


def test_title_only_page_still_gets_a_title() -> None:
    page = clean_html("<html><head><title>Only Title</title></head><body></body></html>")
    assert page.title == "Only Title"
    assert page.links == []


def test_garbage_html_never_crashes() -> None:
    for junk in ("", "\x00\x01 not html at all", "<html><p>unclosed", "<>&"):
        page = clean_html(junk, "https://x.test")
        assert page.text is not None and isinstance(page.links, list)
        assert page.canonical == "" or page.canonical.startswith("http")
