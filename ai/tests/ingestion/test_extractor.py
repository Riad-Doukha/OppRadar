from oppradar_ai.ingestion.extractor import extract_batch, extract_one
from oppradar_ai.schemas import Mode, OpportunityType


def test_fast_path_structured_json():
    raw = {
        "source": "rss:remotive",
        "url": "https://remotive.com/remote-jobs/123",
        "title": "Remote Python Developer",
        "description": "Build APIs in a remote team.",
        "raw": {"company_name": "Acme", "remote": True, "tags": ["python", "go"]},
    }
    opp = extract_one(raw)
    assert opp is not None
    assert opp.title == "Remote Python Developer"
    assert opp.organization == "Acme"
    assert opp.mode is Mode.REMOTE
    assert opp.source_url == raw["url"]
    assert "python" in opp.tags


def test_type_inferred_from_keywords():
    raw = {
        "source": "rss:x",
        "url": "https://x.org/1",
        "title": "Summer Internship in Data Science",
        "description": "Interns will build dashboards.",
        "raw": {},
    }
    opp = extract_one(raw)
    assert opp.type is OpportunityType.INTERNSHIP


def test_records_without_url_are_dropped():
    assert extract_one({"source": "rss:x", "title": "Something", "description": "..."}) is None


def test_extract_batch_skips_duplicates_and_junk():
    base = {
        "source": "rss:x",
        "url": "https://x.org/j/1",
        "title": "Backend Engineer",
        "description": "FastAPI role",
        "raw": {"company_name": "Acme"},
    }
    dup = dict(base, url="https://x.org/j/1?utm_source=feed")
    junk = {"source": "rss:x", "url": "", "title": "", "description": ""}
    results = extract_batch([base, dup, junk])
    # Exact-string URL dupes are skipped; near-dupes (utm variants) survive here
    # on purpose — dedupe.py merges those after extraction.
    assert len(results) == 2
    assert all(o.title == "Backend Engineer" for o in results)


def test_fixture_scam_entry_is_extracted_with_sane_fields(fixture_opportunities):
    # The synthetic scam must still be a well-formed Opportunity (its risk is
    # scored later by scam_check) — extraction never drops valid-looking posts.
    scam = [o for o in fixture_opportunities if "URGENT" in o.title.upper()]
    assert len(scam) == 1
    assert scam[0].organization == "Global Talent Now LLC"
