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
    # Provenance of `deadline`: "rule" = found by the rule-first "Deadline:"
    # line regex, "llm" = model value, "none" = the source states no deadline.
    deadline_source: Literal["rule", "llm", "none"] | None = None
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
    # Free-text "to verify" notes (e.g. "deadline mismatch: ...",
    # "list page - needs detail") shown next to the field confidences.
    review_notes: list[str] = Field(default_factory=list)

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
    # Provenance (sources.yaml): `verified` is true only after the URL was
    # confirmed reachable; `notes` explains what the source provides.
    verified: bool = False
    notes: str = ""


class SourceStats(BaseModel):
    """Per-source outcome of one ingestion run."""

    source: str
    fetched: int = 0
    extracted: int = 0
    new: int = 0
    duplicates: int = 0
    scam_flagged: int = 0
    rejected: int = 0  # is_opportunity=false (listicles, news, advice...)
    list_pages: int = 0  # index pages -> low-confidence "needs detail" records
    fields_filled: int = 0
    pending: int = 0  # no LLM answered (quota/5xx/budget) -> retried next run
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


class RejectedItem(BaseModel):
    """An extracted item that is NOT an opportunity (kept for the report only).

    Never becomes an `Opportunity` record — e.g. a "Top 10 ..." listicle,
    a career-advice article or general news that shares a feed with real calls.
    """

    source: str
    title: str
    url: str = ""
    reason: str = ""


class PendingLLMItem(BaseModel):
    """An item whose extraction awaits a working LLM — never stored.

    A rules-only stand-in would pollute the store with junk records, so when no
    model answers (daily quota gone, transient 5xx, budget spent) the item
    waits in `IngestionReport.pending_llm`. Nothing was cached and nothing was
    stored, so the next run simply extracts it again.
    """

    source: str
    title: str
    url: str = ""
    reason: str = ""


class CallUsage(BaseModel):
    """Free-tier accounting for one kind of remote call in a single run."""

    made: int = 0  # real calls that succeeded (a failure is never "made")
    cached: int = 0  # served from the disk cache (free)
    skipped: int = 0  # blocked by the per-run limit or missing key
    failed_attempts: int = 0  # real calls that failed (5xx, quota, bad reply)
    limit: int = 0  # hard cap on real calls (0 blocks them all)


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
    items_rejected: int = 0  # not an opportunity (listicles, news, advice)
    items_list_pages: int = 0  # low-confidence records from index pages
    # Deadline provenance (rule-first policy: a "Deadline:" line beats the model)
    deadline_from_rule: int = 0
    deadline_from_llm: int = 0
    deadline_mismatches: int = 0  # model disagreed with the rule (rule kept)
    deadline_null: int = 0  # no/rolling deadline in the source (never invented)
    detail_fetches: int = 0  # capped detail-page re-extractions for missing deadlines
    searches: CallUsage = Field(default_factory=CallUsage)
    extractions: CallUsage = Field(default_factory=CallUsage)
    # Median latency of the successful LLM extractions (0.0 = no live call).
    extraction_p50_latency_ms: float = 0.0
    rejected: list[RejectedItem] = Field(default_factory=list)
    pending_llm: list[PendingLLMItem] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)

    @field_validator("searches", "extractions", "pending_llm", mode="before")
    @classmethod
    def _adopt_foreign_usage(cls, value: Any) -> Any:
        """Accept instances of a schema built by another copy of this module.

        Notebook kernels run `%autoreload 2`: edited modules are re-executed
        but unchanged ones keep the old class, so one kernel can hold two live
        `CallUsage` classes. Re-validating from the data keeps the report
        construction working instead of raising a `model_type` error.

        Example:
            >>> report = IngestionReport(
            ...     started_at=datetime.now(timezone.utc),
            ...     finished_at=datetime.now(timezone.utc),
            ...     searches=CallUsage(made=3),
            ... )
            >>> report.searches.made
            3
        """
        if isinstance(value, BaseModel):
            return value.model_dump()
        if isinstance(value, list):
            return [v.model_dump() if isinstance(v, BaseModel) else v for v in value]
        return value


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
class DropReason(str, Enum):
    """Why a hard filter removed an opportunity before it could be scored."""

    EXPIRED = "expired"
    SCAM = "scam"
    TYPE_MISMATCH = "type_mismatch"
    MODE_MISMATCH = "mode_mismatch"
    COUNTRY_MISMATCH = "country_mismatch"
    NO_FUNDING = "no_funding"


class DroppedOpportunity(BaseModel):
    """One opportunity a hard filter removed, with a human explanation."""

    opportunity_id: str
    title: str
    reason: DropReason
    detail: str = ""


class FilterOutcome(BaseModel):
    """Hard-filter pass: what may be scored (`passed`) and what was dropped.

    Missing data never filters — only contradicting data does (an unknown
    country or mode stays, flagged for verification, like a null deadline).
    """

    passed: list[Opportunity] = Field(default_factory=list)
    dropped: list[DroppedOpportunity] = Field(default_factory=list)


class MatchResult(BaseModel):
    """One opportunity scored (0-100) for one profile, with reasons.

    The score is reproducible from its parts:
    `100 * (semantic_weight * semantic_similarity + criteria_weight *
    criteria_ratio + bonus_weight * bonus)` where `criteria_ratio` is
    `met / (met + missed)` (0.5 when no requirement could be checked).
    """

    profile_id: str
    opportunity: Opportunity
    score: float = Field(ge=0, le=100)
    semantic_similarity: float = Field(0.0, ge=0, le=1)
    criteria: list[EligibilityCriterion] = Field(default_factory=list)
    bonus: float = Field(0.0, ge=0, le=1)
    top_reasons: list[str] = Field(default_factory=list)
    unmet_requirements: list[str] = Field(default_factory=list)
    # "llm" only when the rules' reasons were rephrased by the model (score
    # >= notify_threshold, gate open); everything else is rules-only.
    reasons_source: Literal["rules", "llm"] = "rules"


class PhrasedReasons(BaseModel):
    """The LLM's rewording of rule-generated match reasons (facts unchanged).

    The model may only rephrase what the rules produced: it never sees a CV,
    never sees the profile and never invents a new fact.

    Example:
        >>> PhrasedReasons(reasons=["Your Python skills fit this internship"])
        PhrasedReasons(reasons=['Your Python skills fit this internship'])
    """

    reasons: list[str] = Field(min_length=1, max_length=3)


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
class NotificationPrefs(BaseModel):
    """Delivery rules of ONE user, filled from Settings (never hardcoded here).

    Build it with `matching.prefs_from_settings(profile_id)`.

    Example:
        >>> prefs = NotificationPrefs(daily_cap=5, quiet_hours_start=22,
        ...                           quiet_hours_end=8, threshold=70.0)
        >>> prefs.daily_cap, prefs.mode
        (5, <NotificationMode.INSTANT: 'instant'>)
    """

    profile_id: str = "local-user"
    mode: NotificationMode = NotificationMode.INSTANT
    daily_cap: int = Field(ge=0)
    quiet_hours_start: int = Field(ge=0, le=23)
    quiet_hours_end: int = Field(ge=0, le=23)
    threshold: float = Field(ge=0, le=100)

    @field_validator("mode", mode="before")
    @classmethod
    def _digest_is_a_mode(cls, value: object) -> object:
        """Accept the Settings spelling "daily"/"weekly" as NotificationMode.DIGEST.

        Example:
            >>> NotificationPrefs._digest_is_a_mode("daily")
            <NotificationMode.DIGEST: 'digest'>
        """
        if isinstance(value, str) and value in ("daily", "weekly"):
            return NotificationMode.DIGEST
        return value


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


class PrivateProfileFile(BaseModel):
    """The saved data/private/my_profile.json: a Profile plus how it was built.

    `route` records provenance so a consumer (notebook, test) can never be
    ambiguous about where the data came from: "rules-only" = regex extraction
    (nothing left the machine), "llm" = the configured provider was used with
    the user's explicit `--allow-llm` consent.
    """

    profile: Profile
    route: Literal["rules-only", "llm"]
    llm_provider: str = ""  # "" for the rules-only route
    source_file: str = ""
    built_at: datetime
    empty_fields: list[str] = Field(default_factory=list)  # what rules could not fill


class DocumentContent(BaseModel):
    """Raw text read out of one file, plus how it was obtained."""

    file_name: str
    method: Literal["pdf_text", "pdf_ocr", "image_ocr", "docx", "text", "gemini_vision"]
    text: str
    pages: int = 1
    chars: int = 0
    warnings: list[str] = Field(default_factory=list)


class CVExtraction(BaseModel):
    """Structured CV fields, produced by cheap rules plus the LLM."""

    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    country: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)  # fields the LLM marked uncertain
    source_file: str = ""


class CertificateExtraction(BaseModel):
    """Structured fields of a certificate/credential document."""

    title: str = ""
    issuer: str = ""
    holder: str = ""
    issued_on: str | None = None
    hours: int | None = None
    credential_url: str | None = None
    skills: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    source_file: str = ""


class PortfolioExtraction(BaseModel):
    """Structured fields of a portfolio document (projects and links)."""

    full_name: str = ""
    email: str = ""
    links: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    source_file: str = ""


class ExtractionGrade(BaseModel):
    """How close one extraction was to its ground truth.

    Comparison is case-insensitive and whitespace-normalized.
    """

    document: str
    fields_checked: int
    fields_matched: int
    accuracy: float = Field(ge=0, le=1)
    per_field: dict[str, bool] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)  # expected values not found


# --------------------------------------------------------------------------- #
# Ingestion extraction (Phase 3)
# --------------------------------------------------------------------------- #
class OpportunityExtraction(BaseModel):
    """Raw LLM view of one opportunity (deadline kept as written, never guessed).

    `deadline` stays a free string here: `ingestion.extract.parse_deadline`
    converts it to ISO or drops it to None when absent/rolling/unparseable.
    """

    title: str
    organizer: str = ""
    type: OpportunityType = OpportunityType.OTHER
    mode: Literal["remote", "hybrid", "onsite"] | None = None
    location: str = ""
    country: str = ""
    funding: str | None = None
    eligibility: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    summary: str = ""
    deadline: str = ""  # exactly as written in the source; "" when none is stated
    # Gate: false for listicles/rankings, career-advice posts, news — such
    # items are kept in the report's rejected list, never as Opportunity records.
    is_opportunity: bool = True
    not_opportunity_reason: str | None = None
    field_confidences: list[FieldConfidence] = Field(default_factory=list)
