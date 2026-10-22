"""The signed-in user's profile: onboarding wizard (5 steps), review, and CRUD
for the list sections (experiences, certificates) the wizard edits in place.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.auth import User, Writer
from app.models import (
    AboutYouStep,
    AlertsStep,
    Certificate,
    CertificateIn,
    CertificatePatch,
    EducationStep,
    Experience,
    ExperienceIn,
    ExperiencePatch,
    GoalsStep,
    Me,
    SkillsStep,
)
from app.repositories import Repository, get_repository
from app.services import profiles

router = APIRouter()
Repo = Annotated[Repository, Depends(get_repository)]


@router.get("", response_model=Me)
def get_me(user: User, repo: Repo) -> Me:
    """Whole profile + onboarding progress (wizard, review screen, 'Save & exit' resume)."""
    return profiles.load_me(repo, user)


# One autosave endpoint per wizard step. Only the fields sent change; a list
# that is sent (languages, skills, links) replaces the stored list.
@router.patch("/onboarding/about", response_model=Me)
def save_about(user: Writer, repo: Repo, body: AboutYouStep) -> Me:
    """Step 1 · About you."""
    return profiles.save_step(repo, user, 1, body)


@router.patch("/onboarding/education", response_model=Me)
def save_education(user: Writer, repo: Repo, body: EducationStep) -> Me:
    """Step 2 · Education (experiences/certificates use their own endpoints)."""
    return profiles.save_step(repo, user, 2, body)


@router.patch("/onboarding/skills", response_model=Me)
def save_skills(user: Writer, repo: Repo, body: SkillsStep) -> Me:
    """Step 3 · Skills & interests."""
    return profiles.save_step(repo, user, 3, body)


@router.patch("/onboarding/goals", response_model=Me)
def save_goals(user: Writer, repo: Repo, body: GoalsStep) -> Me:
    """Step 4 · Goals & links."""
    return profiles.save_step(repo, user, 4, body)


@router.patch("/onboarding/alerts", response_model=Me)
def save_alerts(user: Writer, repo: Repo, body: AlertsStep) -> Me:
    """Step 5 · Alerts & consent."""
    return profiles.save_step(repo, user, 5, body)


@router.post("/onboarding/complete", response_model=Me)
def complete_onboarding(user: Writer, repo: Repo) -> Me:
    """'Finish setup': 422 with the list of missing required fields, or the completed profile."""
    return profiles.complete(repo, user)


# --------------------------------------------------------------------------- #
# Experiences
# --------------------------------------------------------------------------- #
@router.post("/experiences", response_model=Experience, status_code=status.HTTP_201_CREATED)
def add_experience(user: Writer, repo: Repo, body: ExperienceIn) -> Any:
    repo.ensure_profile(user.id, user.full_name)
    return repo.insert_child("experiences", user.id, body.model_dump())


@router.patch("/experiences/{experience_id}", response_model=Experience)
def edit_experience(user: Writer, repo: Repo, experience_id: UUID, body: ExperiencePatch) -> Any:
    return repo.update_child(
        "experiences", user.id, str(experience_id), body.model_dump(exclude_unset=True)
    )


@router.delete("/experiences/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(user: Writer, repo: Repo, experience_id: UUID) -> Response:
    repo.delete_child("experiences", user.id, str(experience_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Certificates
# --------------------------------------------------------------------------- #
@router.post("/certificates", response_model=Certificate, status_code=status.HTTP_201_CREATED)
def add_certificate(user: Writer, repo: Repo, body: CertificateIn) -> Any:
    repo.ensure_profile(user.id, user.full_name)
    return repo.insert_child("certificates", user.id, body.model_dump())


@router.patch("/certificates/{certificate_id}", response_model=Certificate)
def edit_certificate(user: Writer, repo: Repo, certificate_id: UUID, body: CertificatePatch) -> Any:
    return repo.update_child(
        "certificates", user.id, str(certificate_id), body.model_dump(exclude_unset=True)
    )


@router.delete("/certificates/{certificate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certificate(user: Writer, repo: Repo, certificate_id: UUID) -> Response:
    repo.delete_child("certificates", user.id, str(certificate_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
