# Shared Pydantic schemas — every data structure that crosses a module boundary.
# Called by: all oppradar_ai modules, api.py, notebooks, and the FastAPI backend.

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class OpportunityType(str, Enum):
    SCHOLARSHIP = "scholarship"
    JOB = "job"
    INTERNSHIP = "internship"
    FELLOWSHIP = "fellowship"
    HACKATHON = "hackathon"
    BOOTCAMP = "bootcamp"
    RESEARCH = "research"
    VOLUNTEER = "volunteer"
    COURSE = "course"
    GRANT = "grant"
    OTHER = "other"


class TrustLevel(str, Enum):
    VERIFIED = "verified"  # submitted by a known organisation via the structured form
    LIKELY_SAFE = "likely_safe"
    UNKNOWN = "unknown"
    SUSPICIOUS = "suspicious"
    SCAM = "scam"


class ScamFlag(str, Enum):
    APPLICATION_FEE = "application_fee"
    BANK_OR_ID_REQUEST = "bank_or_id_request"
    FREE_EMAIL_ORGANIZER = "free_email_organizer"
    DOMAIN_MISMATCH = "domain_mismatch"
    UNVERIFIABLE_ORGANIZER = "unverifiable_organizer"
    URGENCY_PRESSURE = "urgency_pressure"
    TOO_GOOD_TO_BE_TRUE = "too_good_to_be_true"


class CriteriaStatus(str, Enum):
    MET = "met"
    MISSED = "missed"
    UNKNOWN = "unknown"


class NotificationMode(str, Enum):
    INSTANT = "instant"
    DIGEST = "digest"


class NotificationStatus(str, Enum):
    SENT = "sent"
    PENDING = "pending"
    SUPPRESSED = "suppressed"


# --------------------------------------------------------------------------- #
# Confidence & eligibility primitives
# --------------------------------------------------------------------------- #
class FieldConfidence(BaseModel):
    """How confident the extractor is about one extracted field."""

    field: str
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False


class EligibilityCriterion(BaseModel):
    """One requirement of an opportunity, checked against a profile."""

    text: str
    status: CriteriaStatus = CriteriaStatus.UNKNOWN
    evidence: str = ""


class ScamFlagDetail(BaseModel):
    flag: ScamFlag
    detail: str = ""


# --------------------------------------------------------------------------- #
# Documents -> profile pieces
# --------------------------------------------------------------------------- #
class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str | None = None
    end_date: str | None = None


class ExperienceItem(BaseModel):
    organization: str = ""
    title: str = ""
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""


class Certificate(BaseModel):
    title: str
    issuer: str = ""
    issued_on: str | None = None
    credential_url: str | None = None
    hours: int | None = None
    source_file: str = ""
    field_confidences: list[FieldConfidence] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: str = ""
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    source_file: str = ""


class PastOpportunity(BaseModel):
    """An opportunity the user already participated in (adds credibility)."""

    title: str
    organization: str = ""
    role: str = ""
    period: str | None = None
    description: str = ""
    source_file: str = ""


class Preferences(BaseModel):
    """What the user is looking for — drives hard filters."""

    types: list[OpportunityType] = Field(default_factory=list)  # empty = any
    modes: list[Literal["remote", "hybrid", "onsite"]] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)  # empty = any
    needs_funding: bool = False


class Profile(BaseModel):
    """The merged, structured picture of one user, built from their documents."""

    user_id: str = "local-user"
    full_name: str = ""
    headline: str = ""
    email: str = ""
    country: str = ""
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    past_opportunities: list[PastOpportunity] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    summary: str = ""  # short text used for embeddings
    completeness: float = Field(0.0, ge=0, le=1)
    completeness_suggestions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    field_confidences: list[FieldConfidence] = Field(default_factory=list)

    def to_verify(self) -> list[FieldConfidence]:
        """Fields whose confidence is below the configured threshold."""
        return [fc for fc in self.field_confidences if fc.needs_review]


# --------------------------------------------------------------------------- #
# Opportunities
# --------------------------------------------------------------------------- #
class Opportunity(BaseModel):
    """One opportunity (scholarship, job, ...) ready for matching and chat."""

    id: str = ""
    title: str
    organizer: str
    type: OpportunityType = OpportunityType.OTHER
    mode: Literal["remote", "hybrid", "onsite"] | None = None
    location: str = ""
    country: str = ""
    language: str = "en"
    deadline: date | None = None
    funding: str | None = None
    eligibility: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    summary: str = ""
    url: str = ""
    source: str = "manual"
    source_checked: datetime | None = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    scam_flags: list[ScamFlagDetail] = Field(default_factory=list)
    added_via: Literal["pipeline", "form", "user"] = "pipeline"
    field_confidences: list[FieldConfidence] = Field(default_factory=list)

    @field_validator("title", "organizer")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @property
    def is_expired(self) -> bool:
        return self.deadline is not None and self.deadline < date.today()

    def to_verify(self) -> list[FieldConfidence]:
        return [fc for fc in self.field_confidences if fc.needs_review]


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
class Source(BaseModel):
    """One configured origin of opportunities (from sources.yaml or a call)."""

    name: str
    url: str
    kind: Literal["rss", "page", "search"] = "rss"
    type_hint: OpportunityType = OpportunityType.OTHER
    language: str = "en"
    country: str = ""
    enabled: bool = True


class SourceStats(BaseModel):
    """Per-source outcome of one ingestion run."""

    source: str
    fetched: int = 0
    extracted: int = 0
    new: int = 0
    duplicates: int = 0
    scam_flagged: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


class IngestionReport(BaseModel):
    """What one pipeline run produced (new records + stats + failures)."""

    started_at: datetime
    finished_at: datetime
    opportunities: list[Opportunity] = Field(default_factory=list)
    per_source: list[SourceStats] = Field(default_factory=list)
    items_fetched: int = 0
    items_new: int = 0
    items_duplicate: int = 0
    items_flagged: int = 0
    failures: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
class MatchResult(BaseModel):
    """One opportunity scored (0-100) for one profile, with reasons."""

    profile_id: str
    opportunity: Opportunity
    score: float = Field(ge=0, le=100)
    semantic_similarity: float = Field(0.0, ge=0, le=1)
    criteria: list[EligibilityCriterion] = Field(default_factory=list)
    bonus: float = Field(0.0, ge=0, le=1)
    top_reasons: list[str] = Field(default_factory=list)
    unmet_requirements: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
class Notification(BaseModel):
    """One alert for the user (or a suppressed/pending one kept for history)."""

    id: str = ""
    profile_id: str
    opportunity_id: str
    title: str
    reason: str = ""  # one-line "why you're seeing this"
    score: float = Field(ge=0, le=100)
    deadline: date | None = None
    url: str = ""
    mode: NotificationMode = NotificationMode.INSTANT
    status: NotificationStatus = NotificationStatus.PENDING
    suppressed_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class Citation(BaseModel):
    """One source grounding an answer."""

    url: str = ""
    title: str = ""
    quote: str = ""


class EligibilityAssessment(BaseModel):
    """Whether the user fits an opportunity, and what's missing."""

    eligible: bool | None = None  # None = not enough info
    met: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatAnswer(BaseModel):
    """One grounded answer from the assistant."""

    answer: str
    language: str = "en"
    citations: list[Citation] = Field(default_factory=list)
    in_source: bool = True  # False => the info simply isn't in the source
    eligibility: EligibilityAssessment | None = None
    extracted_opportunity: Opportunity | None = (
        None  # when the message carried a link/text/screenshot
    )


class ProfileBuildResult(BaseModel):
    """Outcome of merging several documents into one Profile."""

    profile: Profile
    merged_from: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    completeness: float = Field(ge=0, le=1)
    suggestions: list[str] = Field(default_factory=list)
    document_errors: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Generic per-document extraction wrapper (used by documents/)."""

    fields: dict[str, Any] = Field(default_factory=dict)
    confidences: list[FieldConfidence] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    method: Literal["text", "ocr", "vision"] = "text"
    chars_extracted: int = 0
    error: str | None = None
