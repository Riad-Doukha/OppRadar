"""Opportunity ingestion: fetch → extract → dedupe → scam check.

    from oppradar_ai.ingestion import run_pipeline
    opportunities = run_pipeline()
"""

from oppradar_ai.ingestion.dedupe import dedupe
from oppradar_ai.ingestion.extractor import extract_batch
from oppradar_ai.ingestion.fetchers import fetch_all
from oppradar_ai.ingestion.scam_check import check

__all__ = ["run_pipeline", "dedupe", "extract_batch", "fetch_all", "check"]


def run_pipeline(sources: list[str] | None = None):
    """Run the full pipeline for the given (or all enabled) sources.

    A failing source is logged and skipped — this never raises for one bad
    source. Returns de-duplicated Opportunity objects with scam verdicts.
    """
    from datetime import datetime, timezone

    from oppradar_ai.schemas import Opportunity

    raw_records = fetch_all(sources)
    opportunities: list[Opportunity] = extract_batch(raw_records)
    opportunities = dedupe(opportunities)

    now = datetime.now(timezone.utc)
    for opp in opportunities:
        opp.fetched_at = now
        opp.scam = check(opp)
    return opportunities
