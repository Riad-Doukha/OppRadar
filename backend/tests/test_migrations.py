# Static checks on supabase/migrations without a running Postgres: the SQL
# parses with the real Postgres grammar, every public table has RLS, and the
# enumerations match the API models.

import re
import typing
from pathlib import Path

import pytest

from app import models

pglast = pytest.importorskip("pglast")

MIGRATIONS = sorted((Path(__file__).resolve().parents[2] / "supabase" / "migrations").glob("*.sql"))
SQL = "\n".join(p.read_text(encoding="utf-8") for p in MIGRATIONS)


def test_migrations_parse():
    for path in MIGRATIONS:
        pglast.parse_sql(path.read_text(encoding="utf-8"))


def test_every_public_table_has_rls():
    tables = set(re.findall(r"create table (?:if not exists )?public\.(\w+)", SQL))
    with_rls = set(re.findall(r"alter table public\.(\w+) enable row level security", SQL))
    assert tables and tables == with_rls


def _check_values(column: str) -> set[str]:
    match = re.search(rf"\b{column}\s+text[^,]*?check \({column} in \(([^)]*)\)\)", SQL, re.S)
    assert match, column
    return set(re.findall(r"'(\w+)'", match.group(1)))


@pytest.mark.parametrize(
    ("column", "literal"),
    [
        ("education_level", models.EducationLevel),
        ("preferred_location", models.PreferredLocation),
        ("availability", models.Availability),
        ("frequency", models.AlertFrequency),
        ("trust_level", models.TrustLevelName),
    ],
)
def test_enumerations_match_api_models(column, literal):
    assert _check_values(column) == set(typing.get_args(literal))
