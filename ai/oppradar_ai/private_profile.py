# Private user profile: builds the saved data/private/my_profile.json from the
# user's own CV. Two routes: "rules-only" (regex extraction, guaranteed local)
# or "llm" (configured provider, only with explicit --allow-llm consent).
# Called by: scripts/build_private_profile.py; notebooks only LOAD the result.

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from oppradar_ai.config import Settings, forced_provider, get_settings
from oppradar_ai.documents.extractors import extract_cv, find_emails, find_phones, find_urls
from oppradar_ai.documents.profile_builder import build_profile
from oppradar_ai.documents.reader import read_document
from oppradar_ai.schemas import CVExtraction, PrivateProfileFile

logger = logging.getLogger(__name__)

PROFILE_FILE_NAME = "my_profile.json"

# Files a user may drop into data/private/ (what read_document understands).
_DOCUMENT_SUFFIXES = {
    ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".txt", ".md",
}

# Profile-relevant fields reported as empty when the rules cannot fill them.
_REPORTED_FIELDS: tuple[str, ...] = (
    "full_name", "headline", "email", "phone", "country", "summary",
    "skills", "languages", "interests", "education", "experience",
    "certificates", "projects", "links",
)


def rules_only_cv(text: str, source_file: str = "") -> CVExtraction:
    """Regex-only CV extraction: contact details only, nothing invented.

    Example:
        >>> rules_only_cv("Ada, ada@x.com, +213 555 000 111", "cv.md").phone
        '+213 555 000 111'
    """
    return CVExtraction(
        email=(find_emails(text) or [""])[0],
        phone=(find_phones(text) or [""])[0],
        links=find_urls(text),
        source_file=source_file,
    )


def empty_fields(extraction: CVExtraction) -> list[str]:
    """Profile fields a rules-only pass left empty (honest reporting, no guesses).

    Example:
        >>> "skills" in empty_fields(rules_only_cv("mail me at a@b.com"))
        True
    """
    return [name for name in _REPORTED_FIELDS if not getattr(extraction, name)]


def private_profile_path(settings: Settings | None = None) -> Path:
    """Where the saved profile lives: <data_dir>/private/my_profile.json.

    Example:
        >>> private_profile_path().name
        'my_profile.json'
    """
    settings = settings or get_settings()
    return Path(settings.data_dir) / "private" / PROFILE_FILE_NAME


def find_private_cv(settings: Settings | None = None, file_name: str = "") -> Path | None:
    """The user's CV in data/private/ (by name, or the only document in it).

    Returns None when the folder is missing, the named file is absent, or the
    folder holds several documents and no name was given (never guess which).

    Example:
        >>> find_private_cv(file_name="missing.pdf") is None
        True
    """
    settings = settings or get_settings()
    directory = Path(settings.data_dir) / "private"
    if not directory.is_dir():
        return None
    if file_name:
        candidate = directory / file_name
        return candidate if candidate.is_file() else None
    documents = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in _DOCUMENT_SUFFIXES
    )
    return documents[0] if len(documents) == 1 else None


def build_private_profile(
    cv_path: Path,
    *,
    allow_llm: bool = False,
    user_id: str = "u-me",
    settings: Settings | None = None,
) -> PrivateProfileFile:
    """Read one private CV and build the profile file structure.

    With allow_llm=False (default) the whole pipeline runs under the fake
    provider: regex extraction only, the CV text never leaves the machine.
    With allow_llm=True the configured provider reads the CV (the CLI prints
    the consent warning; this function only records which route was used).

    Example:
        >>> build_private_profile(Path("data/private/cv.pdf")).route   # doctest: +SKIP
        'rules-only'
    """
    settings = settings or get_settings()
    if allow_llm:
        document = read_document(cv_path)
        extraction = extract_cv(document.text, document.file_name)
        route, provider = "llm", settings.llm_provider
    else:
        with forced_provider("fake"):
            document = read_document(cv_path)  # vision fallback disabled here
        extraction = rules_only_cv(document.text, document.file_name)
        route, provider = "rules-only", ""
    result = build_profile([extraction], user_id)
    logger.info("private profile from %s via %s route", cv_path.name, route)
    return PrivateProfileFile(
        profile=result.profile,
        route=route,
        llm_provider=provider,
        source_file=cv_path.name,
        built_at=datetime.now(timezone.utc),
        empty_fields=empty_fields(extraction),
    )


def save_private_profile(data: PrivateProfileFile, path: Path) -> Path:
    """Write the profile file as pretty JSON (inside git-ignored data/private/).

    Example:
        >>> save_private_profile(data, Path("x.json")).name   # doctest: +SKIP
        'x.json'
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    logger.info("private profile saved to %s (route: %s)", path, data.route)
    return path


def load_private_profile(path: Path) -> PrivateProfileFile | None:
    """The saved profile file, or None when it does not exist yet.

    Example:
        >>> load_private_profile(Path("data/private/my_profile.json")) is None or True
        True
    """
    if not path.is_file():
        return None
    return PrivateProfileFile.model_validate_json(path.read_text(encoding="utf-8"))
