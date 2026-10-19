"""Profile endpoints — CV upload and profile management."""

from fastapi import APIRouter

router = APIRouter()

# TODO(Riad): POST /profiles/cv accepts a PDF/DOCX upload, saves it outside the
# repo (see .gitignore: uploads/), then calls
# `oppradar_ai.profile.parse_cv(path)` and stores the returned Profile.
