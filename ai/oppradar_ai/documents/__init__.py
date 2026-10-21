# documents/ package: file -> text (reader), text -> structured fields
# (extractors), extractions -> Profile (profile_builder), grading (evaluate).

from oppradar_ai.documents.evaluate import grade_extraction, normalize
from oppradar_ai.documents.extractors import (
    extract_certificate,
    extract_cv,
    extract_portfolio,
    find_emails,
    find_phones,
    find_urls,
)
from oppradar_ai.documents.profile_builder import build_profile
from oppradar_ai.documents.reader import read_document

__all__ = [
    "build_profile",
    "extract_certificate",
    "extract_cv",
    "extract_portfolio",
    "find_emails",
    "find_phones",
    "find_urls",
    "grade_extraction",
    "normalize",
    "read_document",
]
