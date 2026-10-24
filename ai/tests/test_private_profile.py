# Private profile (scripts/build_private_profile.py + private_profile.py):
# rules-only vs consented LLM route, honest empty-field reporting, save/load,
# and the hard privacy guard: nothing under data/private/ may ever be git-tracked.

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

from oppradar_ai.config import get_settings
from oppradar_ai.private_profile import (
    build_private_profile,
    empty_fields,
    find_private_cv,
    load_private_profile,
    private_profile_path,
    rules_only_cv,
    save_private_profile,
)
from oppradar_ai.schemas import PrivateProfileFile

AI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_ROOT.parent

SYNTHETIC_CV = (
    "Synthetic Candidate\nData student\n"
    "Contact: synthetic@example.com, +213 555 000 111\n"
    "Portfolio: https://github.com/synthetic-candidate\n"
)


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """Point DATA_DIR at a throwaway dir and refresh the cached settings."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def private_cv(isolated_data_dir) -> Path:
    """A synthetic CV dropped in data/private/ (never a real one)."""
    path = isolated_data_dir / "private" / "cv_synthetic.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SYNTHETIC_CV, encoding="utf-8")
    return path


@pytest.fixture
def cli():
    """The build_private_profile script, imported so main() can be driven."""
    spec = importlib.util.spec_from_file_location(
        "build_private_profile", AI_ROOT / "scripts" / "build_private_profile.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# Privacy guard (the user's standing requirement)
# --------------------------------------------------------------------------- #
def test_private_dir_is_git_ignored() -> None:
    """.gitignore must ignore every private-data location."""
    rules = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "ai/data/private/" in rules
    assert "data/private/" in rules


def test_no_private_file_is_git_tracked() -> None:
    """FAILS if any file under data/private/ is tracked by git."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--", "ai/data/private", "data/private"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git unavailable")
    assert result.returncode == 0, result.stderr
    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], f"private files tracked by git: {tracked}"


# --------------------------------------------------------------------------- #
# rules-only extraction: what regex can see, and what it honestly cannot
# --------------------------------------------------------------------------- #
def test_rules_only_cv_fills_only_contact_fields() -> None:
    cv = rules_only_cv(SYNTHETIC_CV, "cv_synthetic.md")
    assert cv.email == "synthetic@example.com"
    assert cv.phone == "+213 555 000 111"
    assert cv.links == ["https://github.com/synthetic-candidate"]
    assert cv.skills == [] and cv.full_name == "" and cv.education == []


def test_empty_fields_names_everything_rules_cannot_fill() -> None:
    gaps = empty_fields(rules_only_cv(SYNTHETIC_CV))
    for field in ("full_name", "headline", "skills", "languages", "education", "experience"):
        assert field in gaps
    assert "email" not in gaps and "links" not in gaps


# --------------------------------------------------------------------------- #
# build_private_profile: the consent boundary
# --------------------------------------------------------------------------- #
def test_rules_only_route_never_touches_an_llm(private_cv, monkeypatch) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("the rules-only route must not reach the LLM")

    monkeypatch.setattr("oppradar_ai.private_profile.extract_cv", _boom)
    monkeypatch.setattr("oppradar_ai.llm.get_llm", _boom)
    data = build_private_profile(private_cv, allow_llm=False)
    assert data.route == "rules-only"
    assert data.llm_provider == ""
    assert data.profile.email == "synthetic@example.com"


def test_allow_llm_route_records_the_configured_provider(private_cv) -> None:
    # conftest forces LLM_PROVIDER=fake: the LLM route is exercised, offline.
    data = build_private_profile(private_cv, allow_llm=True)
    assert data.route == "llm"
    assert data.llm_provider == get_settings().llm_provider == "fake"


def test_find_private_cv_needs_exactly_one_document(isolated_data_dir) -> None:
    private = isolated_data_dir / "private"
    private.mkdir(parents=True, exist_ok=True)
    assert find_private_cv() is None  # empty folder
    (private / "a.pdf").write_bytes(b"%PDF-1.4 synthetic")
    assert find_private_cv().name == "a.pdf"
    (private / "b.pdf").write_bytes(b"%PDF-1.4 synthetic")
    assert find_private_cv() is None  # several -> never guess


# --------------------------------------------------------------------------- #
# save / load round trip
# --------------------------------------------------------------------------- #
def test_save_and_load_round_trip(private_cv, isolated_data_dir) -> None:
    data = build_private_profile(private_cv)
    saved = save_private_profile(data, private_profile_path())
    assert saved.parent.name == "private" and saved.is_file()

    loaded = load_private_profile(saved)
    assert isinstance(loaded, PrivateProfileFile)
    assert loaded.route == "rules-only"
    assert loaded.source_file == "cv_synthetic.md"
    assert loaded.profile.email == data.profile.email
    assert loaded.built_at == data.built_at


def test_load_missing_profile_returns_none(isolated_data_dir) -> None:
    assert load_private_profile(private_profile_path()) is None


# --------------------------------------------------------------------------- #
# CLI behaviour
# --------------------------------------------------------------------------- #
def test_cli_rules_only_reports_empty_fields(private_cv, cli, capsys) -> None:
    code = cli.main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "rules-only" in out and "nothing is sent anywhere" in out
    assert "empty    :" in out and "skills" in out
    assert private_profile_path().is_file()


def test_cli_allow_llm_prints_the_consent_warning(private_cv, cli, capsys) -> None:
    code = cli.main(["--allow-llm"])
    out = capsys.readouterr().out
    assert code == 0
    assert "CONSENT: --allow-llm" in out and "cv_synthetic.md" in out
    assert "fake" in out  # the provider that would read the CV (conftest: fake)


def test_cli_refuses_silent_overwrite(private_cv, cli, capsys) -> None:
    assert cli.main([]) == 0
    capsys.readouterr()
    assert cli.main([]) == 1
    out = capsys.readouterr().out
    assert "--force" in out


def test_cli_without_any_cv_says_what_to_do(isolated_data_dir, cli, capsys) -> None:
    code = cli.main([])
    out = capsys.readouterr().out
    assert code == 1
    assert "Drop exactly one file" in out
