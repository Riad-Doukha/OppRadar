# Build data/private/my_profile.json from the user's own CV in data/private/.
# Default route is rules-only (regex; the CV text never leaves the machine).
# --allow-llm is explicit consent: the configured provider then reads the CV.
#
# Usage: python scripts/build_private_profile.py [--file NAME] [--allow-llm] [--force]
# Then:  open notebooks/05_matching.ipynb step 6 to score that profile.

from __future__ import annotations

import argparse
import sys

from oppradar_ai.config import get_settings, setup_logging
from oppradar_ai.private_profile import (
    build_private_profile,
    find_private_cv,
    load_private_profile,
    private_profile_path,
    save_private_profile,
)
from oppradar_ai.schemas import PrivateProfileFile


def _consent_warning(cv_name: str, provider: str, model: str) -> None:
    """Say loudly what --allow-llm is about to do, before anything is sent."""
    via = f"{provider} ({model})" if provider == "gemini" else provider
    print(f"CONSENT: --allow-llm -> the text of {cv_name} will be sent to {via}.")
    print("         Your CV is sent nowhere else, and never committed")
    print("         (data/private/ is git-ignored).")


def _report(data: PrivateProfileFile, out_path: str) -> None:
    """Say what was built, by which route, and which fields stayed empty."""
    via = data.route if data.route == "rules-only" else f"{data.route} ({data.llm_provider})"
    print(f"saved    : {out_path}")
    print(f"route    : {via} | source: {data.source_file}")
    if data.empty_fields:
        print(f"empty    : {', '.join(data.empty_fields)}")
    if data.route == "rules-only":
        print("note     : rules-only fills contact details only; re-run with --allow-llm")
        print("           to let the LLM read skills, education, experience, languages...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build data/private/my_profile.json from your CV.")
    parser.add_argument(
        "--file", default="", help="CV file name inside data/private/ (default: the only one there)"
    )
    parser.add_argument("--allow-llm", action="store_true", help="consent: LLM reads your CV")
    parser.add_argument("--force", action="store_true", help="overwrite an existing profile")
    args = parser.parse_args(argv)
    setup_logging("WARNING")
    settings = get_settings().ensure_dirs()

    out_path = private_profile_path(settings)
    existing = load_private_profile(out_path)
    if existing is not None and not args.force:
        built = f"{existing.built_at:%Y-%m-%d}"
        print(f"{out_path} already exists (route: {existing.route}, built {built}).")
        print("Pass --force to rebuild it.")
        return 1

    cv_path = find_private_cv(settings, args.file)
    if cv_path is None:
        print(f"No CV found in {out_path.parent} (or several, with no --file given).")
        print("Drop exactly one file there (pdf, docx, png, jpg...) or pass --file NAME.")
        return 1

    if args.allow_llm:
        _consent_warning(cv_path.name, settings.llm_provider, settings.gemini_model)
    else:
        print("route    : rules-only (regex; nothing is sent anywhere)")

    data = build_private_profile(cv_path, allow_llm=args.allow_llm, settings=settings)
    saved = save_private_profile(data, out_path)
    _report(data, str(saved))
    return 0


if __name__ == "__main__":
    sys.exit(main())
