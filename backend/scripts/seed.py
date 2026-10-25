"""Seed Supabase with the AI fixtures and the shared demo account.

    cd backend
    python scripts/seed.py               # opportunities from ai/data/fixtures
    python scripts/seed.py --demo        # + the read-only demo user (DEMO_PASSWORD)

Refresh the fixtures first so deadlines are in the future:
    cd ../ai && python scripts/make_fixtures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oppradar_ai.config import get_settings as get_ai_settings  # noqa: E402
from oppradar_ai.schemas import Opportunity  # noqa: E402

from app.auth import CurrentUser  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models import (  # noqa: E402
    AboutYouStep,
    AlertsStep,
    CertificateIn,
    EducationStep,
    ExperienceIn,
    GoalsStep,
    LanguageIn,
    LinkIn,
    SkillIn,
    SkillsStep,
)
from app.repositories import Repository, get_repository  # noqa: E402
from app.services import profiles  # noqa: E402
from app.services.ai import opportunity_row  # noqa: E402
from app.services.db import get_db  # noqa: E402


def seed_opportunities(repo: Repository) -> int:
    fixtures = get_ai_settings().fixtures_dir
    stamp = (fixtures / "generated_on.txt").read_text(encoding="utf-8").strip()
    if stamp != date.today().isoformat():
        print(
            f"WARNING: fixtures were generated on {stamp}; deadlines may be stale "
            "(run `python scripts/make_fixtures.py` in ai/)."
        )
    raw = json.loads((fixtures / "opportunities.json").read_text(encoding="utf-8"))
    rows = [opportunity_row(Opportunity.model_validate(item)) for item in raw]
    return repo.upsert_opportunities(rows)


def seed_demo_user(repo: Repository) -> str:
    """Create (or reuse) the demo auth user and give it the profile from the Figma design."""
    settings = get_settings()
    if not settings.demo_password:
        raise SystemExit("Set DEMO_PASSWORD in .env to create the demo account.")
    client = get_db()
    if client is None:
        raise SystemExit("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).")

    existing = [u for u in client.auth.admin.list_users() if u.email == settings.demo_email]
    attrs = {
        "email": settings.demo_email,
        "password": settings.demo_password,
        "email_confirm": True,
        "app_metadata": {"demo": True},
        "user_metadata": {"full_name": "Amine Benali", "terms_accepted": True},
    }
    if existing:
        user_id = existing[0].id
        client.auth.admin.update_user_by_id(user_id, attrs)
    else:
        user_id = client.auth.admin.create_user(attrs).user.id

    user = CurrentUser(id=str(user_id), email=settings.demo_email, full_name="Amine Benali")
    repo.ensure_profile(user.id, user.full_name)
    repo.update_profile(user.id, {"is_demo": True})
    profiles.save_step(repo, user, 1, AboutYouStep(
        full_name="Amine Benali", birth_year=2003, nationality="Algerian", country="Algeria",
        wilaya="Algiers", languages=[
            LanguageIn(language="Arabic", level="fluent"),
            LanguageIn(language="French", level="good"),
            LanguageIn(language="English", level="fluent"),
        ],
    ))  # fmt: skip
    profiles.save_step(repo, user, 2, EducationStep(
        education_level="licence", field_of_study="Computer Science", institution="ENSIA",
        current_year=3, graduation_year=2028, gpa_value=3.1, gpa_scale=4,
    ))  # fmt: skip
    for table, rows in (
        ("experiences", [
            ExperienceIn(kind="internship", title="Data Analyst Intern", organization="Yassir",
                         location="Algiers", year=2024,
                         description="Built dashboards in Python & SQL."),
            ExperienceIn(kind="hackathon", title="Winner at ENSIA Hack 2024",
                         organization="ENSIA DevClub", year=2024,
                         description="36h AI hackathon, built an RTL chatbot."),
        ]),
        ("certificates", [
            CertificateIn(title="Python for Data Science", issuer="IBM", year=2023),
        ]),
    ):  # fmt: skip
        repo.replace_children(table, user.id, [r.model_dump() for r in rows])
    profiles.save_step(repo, user, 3, SkillsStep(
        skills=[SkillIn(name="Python", level="advanced"), SkillIn(name="SQL", level="intermediate"),
                SkillIn(name="React", level="intermediate"), SkillIn(name="Data analysis"),
                SkillIn(name="Pandas")],
        interests=["AI", "Data", "Volunteering"],
        opportunity_types=["hackathon", "datathon", "competition", "scholarship", "internship"],
        preferred_location="algeria", availability="part_time_10_20",
    ))  # fmt: skip
    profiles.save_step(repo, user, 4, GoalsStep(
        goal="I want to join international hackathons and find a data science internship.",
        links=[LinkIn(kind="linkedin", url="linkedin.com/in/amine-benali"),
               LinkIn(kind="github", url="github.com/aminebz")],
    ))  # fmt: skip
    profiles.save_step(repo, user, 5, AlertsStep(
        email_enabled=True, telegram_enabled=True, threshold=70, frequency="instant",
        consents={"terms_privacy": True, "agent_matching": True},
    ))  # fmt: skip
    profiles.complete(repo, user)
    return user.id


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--demo", action="store_true", help="also create the demo account")
    args = parser.parse_args()

    repo = get_repository()
    print(f"seeded {seed_opportunities(repo)} opportunities")
    if args.demo:
        print(f"demo user ready: {get_settings().demo_email} ({seed_demo_user(repo)})")


if __name__ == "__main__":
    main()
