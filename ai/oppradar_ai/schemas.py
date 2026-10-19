"""SHARED Pydantic schemas — the data contract of the whole AI package.

⚠️  This file is shared between the AI owners (Ahlem & Ikbel) and the backend
owner (Riad). Any change here needs approval from both AI owners — keep diffs
small and backwards compatible.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class OpportunityType(str, Enum):
    INTERNSHIP = "internship"
    JOB = "job"
    SCHOLARSHIP = "scholarship"
    COMPETITION = "competition"
    BOOTCAMP = "bootcamp"
    RESEARCH = "research"
    VOLUNTEER = "volunteer"


class Mode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class ScamLabel(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    SCAM = "scam"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


# --------------------------------------------------------------------------- #
# Opportunities
# --------------------------------------------------------------------------- #
class ScamVerdict(BaseModel):
    label: ScamLabel = ScamLabel.SAFE
    score: float = Field(0.0, ge=0, le=1, description="0 = definitely safe, 1 = definite scam")
    reasons: list[str] = Field(default_factory=list)


class Opportunity(BaseModel):
    """One crawled opportunity, validated and ready for the database."""

    id: str | None = None
    title: str
    organization: str
    type: OpportunityType
    mode: Mode | None = None
    location: str | None = None
    country: str | None = None
    deadline: date | None = None
    salary: str | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "unknown"
    source_url: str
    scam: ScamVerdict | None = None
    fetched_at: datetime | None = None

    @field_validator("title", "organization")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


# --------------------------------------------------------------------------- #
# Profiles (from a parsed CV)
# --------------------------------------------------------------------------- #
class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str | None = None
    end_date: str | None = None


class Experience(BaseModel):
    organization: str = ""
    title: str = ""
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""


class Preferences(BaseModel):
    """What the user is looking for — drives the hard filters."""

    modes: list[Mode] = Field(default_factory=list)          # empty = any
    countries: list[str] = Field(default_factory=list)       # empty = any
    types: list[OpportunityType] = Field(default_factory=list)  # empty = any


class Profile(BaseModel):
    """Structured user profile produced by `profile.cv_parser`."""

    id: str | None = None
    full_name: str = ""
    headline: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    summary: str = ""


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
class MatchResult(BaseModel):
    """One opportunity scored for one profile — best first."""

    opportunity: Opportunity
    profile_id: str | None = None
    score: float = Field(..., ge=0, le=1)
    similarity: float = Field(0.0, ge=0, le=1, description="Embedding cosine similarity")
    skill_overlap: float = Field(0.0, ge=0, le=1, description="Matched / requested skills")
    type_bonus: float = Field(0.0, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Opportunity] = Field(
        default_factory=list, description="Opportunities cited in the answer"
    )
