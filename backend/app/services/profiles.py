"""Profile / onboarding logic shared by the /me routes.

Every onboarding step autosaves partial drafts (`exclude_unset` patches); the
required fields marked * in the design are only enforced by `complete()`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.models import (
    MIN_SKILLS,
    REQUIRED_CONSENTS,
    AboutYouStep,
    AgentSettings,
    AlertsStep,
    EducationStep,
    GoalsStep,
    Me,
    NotificationSettings,
    OnboardingStatus,
    SettingsPatch,
    SkillsStep,
)
from app.repositories import Repository, Row
from app.services import notifications
from app.services.parallel import gather

PROFILE_FIELDS = (
    "full_name", "birth_year", "nationality", "country", "wilaya",
    "education_level", "field_of_study", "institution", "current_year", "graduation_year",
    "gpa_value", "gpa_scale", "interests", "opportunity_types", "preferred_location",
    "availability", "goal",
)  # fmt: skip


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Read
# --------------------------------------------------------------------------- #
def load_me(repo: Repository, user: CurrentUser) -> Me:
    # The profile row must exist first (signup trigger, or created here); the
    # other nine reads are independent and run concurrently.
    profile = repo.ensure_profile(user.id, user.full_name)
    uid = user.id
    r = gather(
        settings=lambda: repo.get_notification_settings(uid),
        skills=lambda: repo.list_children("profile_skills", uid),
        languages=lambda: repo.list_children("profile_languages", uid),
        experiences=lambda: repo.list_children("experiences", uid),
        certificates=lambda: repo.list_children("certificates", uid),
        links=lambda: repo.list_children("profile_links", uid),
        consents=lambda: repo.active_consents(uid),
        documents=lambda: repo.list_documents(uid),
    )
    settings = r["settings"]
    me = Me(
        user_id=user.id,
        email=user.email,
        is_demo=user.is_demo or bool(profile.get("is_demo")),
        is_admin=user.is_admin,
        **{k: profile.get(k) for k in PROFILE_FIELDS if profile.get(k) is not None},
        skills=r["skills"],
        languages=r["languages"],
        experiences=r["experiences"],
        certificates=r["certificates"],
        links=r["links"],
        notifications=NotificationSettings(
            **{k: v for k, v in settings.items() if k in NotificationSettings.model_fields},
            telegram_linked=bool(settings.get("telegram_chat_id")),
        ),
        consents=r["consents"],
        history_retention=profile.get("history_retention") or "12_months",
        agent_settings=AgentSettings.model_validate(profile.get("agent_settings") or {}),
        completeness_suggestions=profile.get("completeness_suggestions") or [],
        onboarding=OnboardingStatus(
            step=profile.get("onboarding_step") or 1,
            completed_at=profile.get("onboarding_completed_at"),
            agent_started_at=profile.get("agent_started_at"),
        ),
    )
    me.onboarding.missing = missing_required(me, has_documents=bool(r["documents"]))
    me.completeness = completeness(me)
    return me


def missing_required(me: Me, has_documents: bool = False) -> list[str]:
    """Required (*) fields still empty, as 'step.field' keys the UI can highlight."""
    checks: list[tuple[str, Any]] = [
        ("about.full_name", me.full_name.strip()),
        ("about.birth_year", me.birth_year),
        ("about.nationality", me.nationality),
        ("about.country", me.country),
        ("about.wilaya", me.wilaya),
        ("education.education_level", me.education_level),
        ("education.field_of_study", me.field_of_study),
        ("education.current_or_graduation_year", me.current_year or me.graduation_year),
        ("skills.skills", len(me.skills) >= MIN_SKILLS),
        ("skills.interests", me.interests),
        ("skills.opportunity_types", me.opportunity_types),
        ("skills.preferred_location", me.preferred_location),
        ("goals.goal", me.goal),
        ("alerts.channel", me.notifications.email_enabled or me.notifications.telegram_enabled),
    ]
    required_consents = list(REQUIRED_CONSENTS) + (["ai_cv_processing"] if has_documents else [])
    checks += [(f"alerts.consent.{kind}", kind in me.consents) for kind in required_consents]
    return [key for key, value in checks if not value]


def completeness(me: Me) -> float:
    """Share of profile sections filled (required and optional), 0..1."""
    filled = [
        bool(me.full_name), bool(me.birth_year), bool(me.nationality), bool(me.country),
        bool(me.wilaya), bool(me.languages), bool(me.education_level), bool(me.field_of_study),
        bool(me.institution), bool(me.current_year or me.graduation_year),
        bool(me.experiences or me.certificates), len(me.skills) >= MIN_SKILLS,
        any(s.level for s in me.skills), bool(me.interests), bool(me.opportunity_types),
        bool(me.preferred_location), bool(me.goal), bool(me.links),
    ]  # fmt: skip
    return round(sum(filled) / len(filled), 3)


# --------------------------------------------------------------------------- #
# Write
# --------------------------------------------------------------------------- #
def save_step(repo: Repository, user: CurrentUser, step: int, body: Any) -> Me:
    profile = repo.ensure_profile(user.id, user.full_name)
    data: dict[str, Any] = body.model_dump(exclude_unset=True)
    updates: Row = {}

    if isinstance(body, AboutYouStep):
        if "languages" in data:
            repo.replace_children("profile_languages", user.id, data.pop("languages") or [])
        updates.update(data)
    elif isinstance(body, EducationStep):
        merged = {k: data.get(k, profile.get(k)) for k in ("gpa_value", "gpa_scale")}
        if (merged["gpa_value"] is None) != (merged["gpa_scale"] is None):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "GPA needs both a value and a scale (/4 or /20).",
            )
        if merged["gpa_value"] is not None and merged["gpa_value"] > merged["gpa_scale"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"GPA {merged['gpa_value']} is above the /{merged['gpa_scale']} scale.",
            )
        updates.update(data)
    elif isinstance(body, SkillsStep):
        if "skills" in data:
            skills = _dedupe_by(data.pop("skills") or [], "name")
            repo.replace_children("profile_skills", user.id, skills)
        updates.update(data)
    elif isinstance(body, GoalsStep):
        if "links" in data:
            repo.replace_children("profile_links", user.id, data.pop("links") or [])
        updates.update(data)
    elif isinstance(body, AlertsStep):
        _save_alerts(repo, user.id, data)
        notifications.invalidate(user.id)  # alert rules may have changed

    if profile.get("onboarding_completed_at") is None:
        updates["onboarding_step"] = max(step, profile.get("onboarding_step") or 1)
    if updates:
        repo.update_profile(user.id, updates)
    return _refresh_completeness(repo, user)


def _save_alerts(repo: Repository, user_id: str, data: dict[str, Any]) -> None:
    consents = data.pop("consents", None) or {}
    if data.pop("clear_quiet_hours", False):
        data["quiet_start"] = data["quiet_end"] = None
    if ("quiet_start" in data) != ("quiet_end" in data):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Quiet hours need both a start and an end time.",
        )
    if data:
        repo.update_notification_settings(user_id, data)
    for kind, granted in consents.items():
        (repo.grant_consent if granted else repo.revoke_consent)(user_id, kind)


def _refresh_completeness(repo: Repository, user: CurrentUser) -> Me:
    me = load_me(repo, user)
    repo.update_profile(user.id, {"completeness": me.completeness})
    return me


def complete(repo: Repository, user: CurrentUser) -> Me:
    me = load_me(repo, user)
    if me.onboarding.missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "Some required fields are still empty.", "missing": me.onboarding.missing},
        )
    if me.onboarding.completed_at is None:
        repo.update_profile(user.id, {"onboarding_completed_at": _now(), "onboarding_step": 5})
        me = load_me(repo, user)
    return me


def _dedupe_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        if row[key].lower() not in seen:
            seen.add(row[key].lower())
            out.append(row)
    return out


def save_settings(repo: Repository, user: CurrentUser, body: SettingsPatch) -> Me:
    """Settings -> Privacy & AI retention and Agent & sources (merged into the stored jsonb)."""
    profile = repo.ensure_profile(user.id, user.full_name)
    updates: Row = {}
    if body.history_retention:
        updates["history_retention"] = body.history_retention
    if body.agent:
        current = AgentSettings.model_validate(profile.get("agent_settings") or {}).model_dump()
        patch = body.agent.model_dump(exclude_none=True)
        if "source_groups" in patch:
            patch["source_groups"] = {**current["source_groups"], **patch["source_groups"]}
        updates["agent_settings"] = AgentSettings.model_validate({**current, **patch}).model_dump()
    if updates:
        repo.update_profile(user.id, updates)
    return load_me(repo, user)


def delete_account(repo: Repository, user: CurrentUser) -> None:
    """Delete stored files, then the auth user; every table cascades from it."""
    for doc in repo.list_documents(user.id):
        repo.delete_file(doc["storage_path"])
    repo.delete_user(user.id)
