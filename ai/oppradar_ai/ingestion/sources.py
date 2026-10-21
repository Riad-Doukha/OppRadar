# sources.yaml loader: real, public sources only. Every row MUST carry
# `verified` (was the URL confirmed reachable — never invent URLs) and
# `notes` (what the source provides / why it is unverified).
# Called by: ingestion/pipeline.py, api.py, notebook 03_discovery.

from __future__ import annotations

from pathlib import Path

import yaml

from oppradar_ai.config import get_settings
from oppradar_ai.schemas import Source

_REQUIRED_KEYS = ("verified", "notes")


def load_sources(path: Path | None = None) -> list[Source]:
    """Parse sources.yaml into validated Source models.

    Example:
        >>> sources = load_sources()
        >>> all(s.url.startswith("http") for s in sources)
        True
    """
    path = path or get_settings().sources_path
    if not path.exists():
        raise FileNotFoundError(f"sources file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("sources", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected a 'sources' list")
    for index, row in enumerate(rows, start=1):
        _check_row(path, index, row)
    sources = [Source.model_validate(row) for row in rows]
    _check_unique(path, sources)
    return sources


def _check_row(path: Path, index: int, row: object) -> None:
    if not isinstance(row, dict):
        raise ValueError(f"{path}: source #{index} is not a mapping")
    missing = sorted(set(_REQUIRED_KEYS) - set(row))
    if missing:
        raise ValueError(f"{path}: source #{index} is missing {missing}")
    url = str(row.get("url", ""))
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"{path}: source #{index} has a non-http url: {url!r}")


def _check_unique(path: Path, sources: list[Source]) -> None:
    names = [s.name for s in sources]
    dupes = sorted({name for name in names if names.count(name) > 1})
    if dupes:
        raise ValueError(f"{path}: duplicate source names: {dupes}")
