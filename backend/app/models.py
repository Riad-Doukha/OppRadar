"""API models: what the frontend sends and receives.

Field sets follow the Figma onboarding screens; allowed values mirror the
check constraints in supabase/migrations/0001_initial_schema.sql. Opportunity
shapes come straight from oppradar_ai.schemas.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

EducationLevel = Literal["bac", "licence", "master", "engineer", "phd", "other"]
PreferredLocation = Literal["algeria", "abroad", "remote", "anywhere"]
Availability = Literal["full_time", "part_time_10_20", "under_10h", "flexible"]
SkillLevel = Literal["beginner", "intermediate", "advanced"]
LanguageLevel = Literal["basic", "good", "fluent"]
ExperienceKind = Literal["internship", "hackathon", "job", "volunteer", "competition", "other"]
LinkKind = Literal["linkedin", "github", "portfolio", "other"]
AlertFrequency = Literal["instant", "daily", "weekly"]
ConsentKind = Literal[
    "terms_privacy", "agent_matching", "ai_cv_processing",
    "ai_drafts", "chat_history", "anonymized_stats",  # Settings -> Privacy & AI
]  # fmt: skip
HistoryRetention = Literal["12_months", "never"]
SourceGroup = Literal["universities", "companies", "events", "international"]
DocumentKind = Literal["cv", "certificate", "portfolio"]
DocumentStatus = Literal["queued", "reading", "extracting", "done", "failed"]
OpportunityTypeName = Literal[
    "scholarship", "job", "internship", "fellowship", "hackathon", "datathon",
    "competition", "bootcamp", "research", "volunteer", "course", "grant", "other",
]  # fmt: skip
TrustLevelName = Literal["verified", "likely_safe", "unknown", "suspicious", "scam"]

REQUIRED_CONSENTS: tuple[ConsentKind, ...] = ("terms_privacy", "agent_matching")
MIN_SKILLS = 3


def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


class _Out(BaseModel):
    """Base for response models: fields with defaults are always present in
    responses, so the OpenAPI schema (and the generated frontend types) mark
    them required."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class _In(_Out):
    """Base for request bodies: trims strings, rejects unknown fields.
    (Inherits _Out only for the read models built on these, e.g. Skill.)"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# Read models built from DB rows ignore the extra columns (user_id, position, ...).
_READ = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --------------------------------------------------------------------------- #
# Profile pieces
# --------------------------------------------------------------------------- #
class SkillIn(_In):
    name: str = Field(min_length=1, max_length=60)
    level: SkillLevel | None = None


class Skill(SkillIn):
    model_config = _READ

    id: UUID | None = None


class LanguageIn(_In):
    language: str = Field(min_length=1, max_length=40)
    level: LanguageLevel = "good"


class Language(LanguageIn):
    model_config = _READ

    id: UUID | None = None


class LinkIn(_In):
    kind: LinkKind
    url: str = Field(min_length=1, max_length=300)

    @field_validator("url")
    @classmethod
    def _normalise_url(cls, value: str) -> str:
        # The design accepts "linkedin.com/in/x" without a scheme.
        if "://" not in value:
            value = f"https://{value}"
        HttpUrl(value)  # raises on garbage
        return value


class Link(LinkIn):
    model_config = _READ

    id: UUID | None = None


class ExperienceIn(_In):
    kind: ExperienceKind = "other"
    title: str = Field(min_length=1, max_length=150)
    organization: str = Field("", max_length=150)
    location: str = Field("", max_length=100)
    year: int | None = Field(None, ge=1950, le=2100)
    description: str = Field("", max_length=1000)


class ExperiencePatch(_In):
    kind: ExperienceKind | None = None
    title: str | None = Field(None, min_length=1, max_length=150)
    organization: str | None = Field(None, max_length=150)
    location: str | None = Field(None, max_length=100)
    year: int | None = Field(None, ge=1950, le=2100)
    description: str | None = Field(None, max_length=1000)


class Experience(ExperienceIn):
    model_config = _READ

    id: UUID


class CertificateIn(_In):
    title: str = Field(min_length=1, max_length=150)
    issuer: str = Field("", max_length=150)
    year: int | None = Field(None, ge=1950, le=2100)
    credential_url: str | None = Field(None, max_length=300)


class CertificatePatch(_In):
    title: str | None = Field(None, min_length=1, max_length=150)
    issuer: str | None = Field(None, max_length=150)
    year: int | None = Field(None, ge=1950, le=2100)
    credential_url: str | None = Field(None, max_length=300)


class Certificate(CertificateIn):
    model_config = _READ

    id: UUID


class NotificationSettings(_Out):
    email_enabled: bool = True
    telegram_enabled: bool = False
    telegram_linked: bool = False
    threshold: int = Field(70, ge=50, le=100)
    frequency: AlertFrequency = "instant"
    quiet_start: time | None = time(22, 0)
    quiet_end: time | None = time(7, 0)
    # Settings -> Notifications -> Alert rules
    rule_new_match: bool = True
    rule_deadline_reminders: bool = True
    rule_application_updates: bool = True
    rule_weekly_digest: bool = True
    rule_profile_tips: bool = False
    bundle_non_urgent: bool = False


_SOURCE_GROUPS = ("universities", "companies", "events", "international")


class AgentSettings(_Out):
    """Settings -> Agent & sources. Stored as profiles.agent_settings (jsonb);
    honoured by the scan pipeline once it ships."""

    auto_scan: bool = True
    scope: Literal["all_dz", "remote"] = "all_dz"
    languages: list[Literal["en", "fr", "ar"]] = Field(default_factory=lambda: ["en", "fr", "ar"])
    min_score: int = Field(55, ge=0, le=100)
    check_eligibility: bool = True
    auto_save_high_matches: bool = True
    draft_applications: bool = True
    source_groups: dict[SourceGroup, bool] = Field(
        default_factory=lambda: dict.fromkeys(_SOURCE_GROUPS, True)
    )


class AgentSettingsPatch(_In):
    auto_scan: bool | None = None
    scope: Literal["all_dz", "remote"] | None = None
    languages: list[Literal["en", "fr", "ar"]] | None = Field(None, min_length=1)
    min_score: int | None = Field(None, ge=0, le=100)
    check_eligibility: bool | None = None
    auto_save_high_matches: bool | None = None
    draft_applications: bool | None = None
    source_groups: dict[SourceGroup, bool] | None = None


class SettingsPatch(_In):
    """PATCH /me/settings: Privacy & AI retention + Agent & sources."""

    history_retention: HistoryRetention | None = None
    agent: AgentSettingsPatch | None = None
    locale: Literal["en", "fr", "ar"] | None = None  # interface language (emails follow it)


# --------------------------------------------------------------------------- #
# Onboarding steps — every field optional so the UI can autosave drafts
# --------------------------------------------------------------------------- #
class AboutYouStep(_In):
    """Step 1 · About you."""

    full_name: str | None = Field(None, max_length=120)
    birth_year: int | None = Field(None, ge=1940, le=2020)
    nationality: str | None = Field(None, max_length=60)
    country: str | None = Field(None, max_length=60)
    wilaya: str | None = Field(None, max_length=60)
    languages: list[LanguageIn] | None = Field(None, max_length=10)


class EducationStep(_In):
    """Step 2 · Education & experience (experiences/certificates have their own CRUD)."""

    education_level: EducationLevel | None = None
    field_of_study: str | None = Field(None, max_length=120)
    institution: str | None = Field(None, max_length=150)
    current_year: int | None = Field(None, ge=1, le=10)
    graduation_year: int | None = Field(None, ge=1950, le=2100)
    gpa_value: float | None = Field(None, ge=0)
    gpa_scale: Literal[4, 20] | None = None

    @model_validator(mode="after")
    def _gpa_within_scale(self) -> EducationStep:
        if (
            self.gpa_value is not None
            and self.gpa_scale is not None
            and self.gpa_value > self.gpa_scale
        ):
            raise ValueError(f"GPA {self.gpa_value} is above the /{self.gpa_scale} scale")
        return self


class SkillsStep(_In):
    """Step 3 · Skills & interests."""

    skills: list[SkillIn] | None = Field(None, max_length=40)
    interests: list[str] | None = Field(None, max_length=30)
    opportunity_types: list[OpportunityTypeName] | None = None
    preferred_location: PreferredLocation | None = None
    availability: Availability | None = None

    @field_validator("interests")
    @classmethod
    def _clean_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _dedupe_ci([_strip(v) for v in value if _strip(v)])


class GoalsStep(_In):
    """Step 4 · Goals & links."""

    goal: str | None = Field(None, min_length=20, max_length=300)
    links: list[LinkIn] | None = Field(None, max_length=8)


class AlertsStep(_In):
    """Step 5 · Alerts & consent."""

    email_enabled: bool | None = None
    telegram_enabled: bool | None = None
    threshold: int | None = Field(None, ge=50, le=100)
    frequency: AlertFrequency | None = None
    quiet_start: time | None = None
    quiet_end: time | None = None
    clear_quiet_hours: bool = False
    consents: dict[ConsentKind, bool] | None = None
    # Settings -> Notifications (not shown in the wizard)
    rule_new_match: bool | None = None
    rule_deadline_reminders: bool | None = None
    rule_application_updates: bool | None = None
    rule_weekly_digest: bool | None = None
    rule_profile_tips: bool | None = None
    bundle_non_urgent: bool | None = None


# --------------------------------------------------------------------------- #
# Read model
# --------------------------------------------------------------------------- #
class OnboardingStatus(_Out):
    step: int
    completed_at: datetime | None = None
    agent_started_at: datetime | None = None
    missing: list[str] = Field(default_factory=list)  # required fields still empty


class Me(_Out):
    """Everything the onboarding wizard and the profile review screen show."""

    user_id: UUID
    email: str = ""
    is_demo: bool = False
    is_admin: bool = False
    locale: Literal["en", "fr", "ar"] = "en"
    full_name: str = ""
    birth_year: int | None = None
    nationality: str | None = None
    country: str | None = None
    wilaya: str | None = None
    education_level: EducationLevel | None = None
    field_of_study: str | None = None
    institution: str | None = None
    current_year: int | None = None
    graduation_year: int | None = None
    gpa_value: float | None = None
    gpa_scale: int | None = None
    interests: list[str] = Field(default_factory=list)
    opportunity_types: list[OpportunityTypeName] = Field(default_factory=list)
    preferred_location: PreferredLocation | None = None
    availability: Availability | None = None
    goal: str | None = None
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    consents: list[ConsentKind] = Field(default_factory=list)  # currently granted
    history_retention: HistoryRetention = "12_months"
    agent_settings: AgentSettings = Field(default_factory=AgentSettings)
    completeness: float = 0.0
    completeness_suggestions: list[str] = Field(default_factory=list)
    onboarding: OnboardingStatus


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Notifications (bell + Notifications page)
# --------------------------------------------------------------------------- #
NotificationKind = Literal[
    "match", "deadline", "application", "digest", "tip", "security", "system"
]
NotificationTab = Literal["all", "matches", "deadlines", "applications", "system"]


class NotificationOut(_Out):
    model_config = _READ

    id: UUID
    kind: NotificationKind = "match"
    title: str
    body: str = ""
    opportunity_id: UUID | None = None
    score: float | None = None
    deadline: date | None = None
    action_url: str | None = None
    read: bool = False
    # Match alerts: "pending" = held by quiet hours, the daily limit or the digest.
    status: Literal["sent", "pending", "suppressed"] = "sent"
    created_at: datetime


class NotificationList(_Out):
    items: list[NotificationOut]
    unread: int


class ReadRequest(_In):
    ids: list[UUID] | None = None  # None = mark everything read


class Document(_Out):
    id: UUID
    kind: DocumentKind
    file_name: str
    size_bytes: int
    status: DocumentStatus
    read_method: str | None = None
    warnings: list[str] = Field(default_factory=list)
    extraction: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime


class CVPrefill(_Out):
    """Values found in a CV, shaped like the onboarding steps they pre-fill."""

    about: AboutYouStep = Field(default_factory=AboutYouStep)
    education: EducationStep = Field(default_factory=EducationStep)
    skills: SkillsStep = Field(default_factory=SkillsStep)
    goals: GoalsStep = Field(default_factory=GoalsStep)
    experiences: list[ExperienceIn] = Field(default_factory=list)
    certificates: list[CertificateIn] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)


class DocumentDetail(Document):
    prefill: CVPrefill | None = None


# --------------------------------------------------------------------------- #
# Opportunities
# --------------------------------------------------------------------------- #
class OpportunityOut(_Out):
    id: UUID
    external_id: str | None = None
    title: str
    organizer: str
    type: OpportunityTypeName
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
    source: str = ""
    trust_level: TrustLevelName = "unknown"
    scam_flags: list[dict[str, Any]] = Field(default_factory=list)
    added_via: str = "pipeline"
    created_at: datetime | None = None
    deadline_source: Literal["rule", "llm", "none"] | None = None
    review_notes: list[str] = Field(default_factory=list)  # extractor's "needs review"


class OpportunityInput(_In):
    """Fields an organisation (submission form) or an admin fills in."""

    title: str = Field(min_length=3, max_length=200)
    organizer: str = Field(min_length=2, max_length=200)
    type: OpportunityTypeName = "other"
    mode: Literal["remote", "hybrid", "onsite"] | None = None
    location: str = Field("", max_length=120)
    country: str = Field("", max_length=60)
    language: Literal["en", "fr", "ar"] = "en"
    deadline: date | None = None
    funding: str | None = Field(None, max_length=120)
    eligibility: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list, max_length=20
    )
    benefits: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        default_factory=list, max_length=20
    )
    summary: str = Field("", max_length=3000)
    url: str = Field(min_length=1, max_length=500)

    @field_validator("url")
    @classmethod
    def _official_url(cls, value: str) -> str:
        if "://" not in value:
            value = f"https://{value}"
        HttpUrl(value)  # raises on garbage
        return value


class SubmissionIn(OpportunityInput):
    """Organisation submission: reviewed by an admin before it goes public."""

    contact_email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdminOpportunityIn(OpportunityInput):
    trust_level: TrustLevelName = "likely_safe"


class OpportunityPatch(_In):
    """Admin edit: only the fields sent are changed."""

    title: str | None = Field(None, min_length=3, max_length=200)
    organizer: str | None = Field(None, min_length=2, max_length=200)
    type: OpportunityTypeName | None = None
    mode: Literal["remote", "hybrid", "onsite"] | None = None
    location: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=60)
    language: Literal["en", "fr", "ar"] | None = None
    deadline: date | None = None
    funding: str | None = Field(None, max_length=120)
    eligibility: list[Annotated[str, Field(min_length=1, max_length=300)]] | None = Field(
        None, max_length=20
    )
    benefits: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        None, max_length=20
    )
    summary: str | None = Field(None, max_length=3000)
    url: str | None = Field(None, min_length=1, max_length=500)
    trust_level: TrustLevelName | None = None

    @field_validator("url")
    @classmethod
    def _official_url(cls, value: str | None) -> str | None:
        return None if value is None else OpportunityInput._official_url(value)


ReviewStatus = Literal["pending", "approved", "rejected"]


class ReviewIn(_In):
    status: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=500)  # shown to the submitter
    trust_level: TrustLevelName | None = None  # set at the same time (optional)


class ReviewedOpportunity(OpportunityOut):
    """An opportunity with its review state (admin screens, "My submissions")."""

    review_status: ReviewStatus = "approved"
    review_note: str | None = None
    reviewed_at: datetime | None = None
    contact_email: str | None = None
    submitted_by: UUID | None = None
    updated_at: datetime | None = None


class ReviewedOpportunityPage(_Out):
    items: list[ReviewedOpportunity]
    total: int
    limit: int
    offset: int


class AdminStats(_Out):
    pending: int
    flagged: int  # approved and suspicious or scam
    published: int  # approved, not expired
    rejected: int


class OpportunityPage(_Out):
    items: list[OpportunityOut]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------------- #
# Applications (Apply assistant + Applications page)
# --------------------------------------------------------------------------- #
ApplicationStatus = Literal["draft", "submitted", "accepted", "rejected", "withdrawn"]


class ApplicationPatch(_In):
    status: ApplicationStatus | None = None
    reference: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=2000)


class ApplicationOut(_Out):
    model_config = _READ

    id: UUID
    opportunity_id: UUID
    status: ApplicationStatus
    reference: str | None = None
    notes: str = ""
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    opportunity: OpportunityOut | None = None


# --------------------------------------------------------------------------- #
# Ask the agent (chat)
# --------------------------------------------------------------------------- #
class ChatRequest(_In):
    message: str = Field(min_length=1, max_length=1000)
    opportunity_id: UUID | None = None  # "Ask the agent about this" from an opportunity page


class Eligibility(_Out):
    eligible: bool | None = None  # None = not enough information
    met: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ChatMessageOut(_Out):
    model_config = _READ

    id: UUID | None = None  # None when chat history isn't kept (consent off)
    role: Literal["user", "assistant"]
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[OpportunityOut] = Field(default_factory=list)
    in_source: bool = True  # False: the answer isn't stated in the source — show it as such
    # An opportunity the AI read from a pasted link/text that OppRadar doesn't have yet.
    extracted: dict[str, Any] | None = None
    eligibility: Eligibility | None = None
    created_at: datetime


class ChatHistory(_Out):
    messages: list[ChatMessageOut]
    saved: bool  # False = chat_history consent is off; nothing is stored
    ai_available: bool = False  # True when the AI wrote this answer (else keyword search)


# --------------------------------------------------------------------------- #
# Premium early access (payments not live yet)
# --------------------------------------------------------------------------- #
PremiumPlan = Literal["premium", "clubs"]
Billing = Literal["monthly", "yearly"]
PaymentMethod = Literal["cib", "edahabia", "baridimob", "ccp"]


class ReservationIn(_In):
    plan: PremiumPlan = "premium"
    billing: Billing = "monthly"
    payment_method: PaymentMethod | None = None


class Reservation(_Out):
    model_config = _READ

    plan: PremiumPlan
    billing: Billing
    payment_method: PaymentMethod | None = None
    position: int  # place in the early-access queue (1 = first)
    created_at: datetime


class PremiumStatus(_Out):
    current_plan: Literal["free"] = "free"  # nobody can pay yet
    payments_live: bool = False
    reservation: Reservation | None = None
    reservations_total: int = 0


class OpportunityFilters(BaseModel):
    q: str | None = None
    types: list[OpportunityTypeName] = Field(default_factory=list)
    modes: list[Literal["remote", "hybrid", "onsite"]] = Field(default_factory=list)
    country: str | None = None
    trust_levels: list[TrustLevelName] = Field(default_factory=list)
    include_expired: bool = False
    deadline_before: date | None = None
    # Per-user feeds: None = no restriction, [] = nothing ("Saved" with no saves).
    ids: list[str] | None = None
    exclude_ids: list[str] = Field(default_factory=list)  # "Not interested"
    created_after: datetime | None = None  # "New" badge / new-today count
    match_any: bool = False  # q matches ANY word (chat keyword search) instead of all
    url_like: str | None = None  # chat: a pasted link, matched against opportunities.url
    limit: int = Field(20, ge=1, le=1000)  # internal: routers cap user requests at 100
    offset: int = Field(0, ge=0)


# --------------------------------------------------------------------------- #
# Dashboard feed (per-user view of opportunities)
# --------------------------------------------------------------------------- #
FeedTab = Literal["for_you", "closing", "saved"]


class Criterion(_Out):
    """One requirement checked against the profile (AI matcher)."""

    text: str
    status: Literal["met", "unmet", "unknown"] = "unknown"
    evidence: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _from_ai(cls, v: object) -> object:
        return "unmet" if v == "missed" else v  # the AI's CriteriaStatus.MISSED


class MatchInfo(_Out):
    score: float  # 0-100
    top_reasons: list[str] = Field(default_factory=list)
    unmet_requirements: list[str] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    reasons_source: Literal["rules", "llm"] = "rules"


class MyOpportunity(OpportunityOut):
    """An opportunity plus this user's state and, once their agent has scanned,
    the AI match (score, reasons, eligibility checklist)."""

    saved: bool = False
    dismissed: bool = False
    is_new: bool = False
    match: MatchInfo | None = None


class MyOpportunityPage(_Out):
    tab: FeedTab
    items: list[MyOpportunity]
    total: int
    limit: int
    offset: int


class DashboardStats(_Out):
    for_you: int
    closing_this_week: int
    saved: int
    new_today: int
    applications: int = 0
    agent_started_at: datetime | None = None
    matching_available: bool = False  # the agent is on and matching this profile
    matched: int = 0  # opportunities with a match score
    last_scan_at: datetime | None = None


class AgentStatus(_Out):
    status: Literal["waiting_for_matcher", "running"]
    agent_started_at: datetime


class ScanResult(_Out):
    """One matching pass for a user ("Run scan now", agent start)."""

    scanned: int  # open opportunities checked
    matches: int  # that passed the hard filters and got a score
    notifications_sent: int
    finished_at: datetime


class IngestionRun(_Out):
    """One ingestion run (admin "sync" screen); report = IngestionReport counters."""

    model_config = _READ

    id: UUID
    trigger: Literal["manual", "scheduled"] = "manual"
    started_at: datetime
    finished_at: datetime
    items_fetched: int = 0
    items_new: int = 0
    items_saved: int = 0
    items_flagged: int = 0
    report: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DemoSession(_Out):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


def _dedupe_ci(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out
