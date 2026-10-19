"""Opportunity endpoints.

List/filter/search opportunities; trigger ingestion on demand.
"""

from fastapi import APIRouter

router = APIRouter()

# TODO(Riad): wire to Supabase via app.services.db, and call
# `oppradar_ai.ingestion.run_pipeline()` for the on-demand ingest endpoint.
