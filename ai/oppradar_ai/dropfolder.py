# Drop folder (data/live_feed/): a JSON or HTML file dropped there is picked up
# on the next agent cycle as a new opportunity. Files are never deleted — parsed
# ones move to consumed/, broken ones to quarantine/, half-written ones wait.
# Called by: agent.py (every cycle), notebooks/08_background_agent.

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.ingestion.budget import RunBudget
from oppradar_ai.ingestion.clean import clean_html
from oppradar_ai.ingestion.extract import extract_record, opportunity_id
from oppradar_ai.schemas import DropFolderReport, Opportunity

logger = logging.getLogger(__name__)

JSON_SUFFIXES = {".json"}
HTML_SUFFIXES = {".html", ".htm"}
# A file younger than this may still be mid-write: leave it for the next cycle.
STABLE_SECONDS = 0.5


def scan_drop_folder(
    settings: Settings | None = None,
    *,
    budget: RunBudget | None = None,
) -> DropFolderReport:
    """Scan the drop folder once: parse every settled file, then move it aside.

    JSON files hold structured opportunities (one object, a list, or a
    `{"opportunities": [...]}` wrapper) and are validated as-is — no model is
    involved. HTML files go through the same cleaned -> extracted path as web
    pages: rules first, the model only when the cost gate is open.

    Example:
        >>> report = scan_drop_folder()                     # doctest: +SKIP
        >>> report.consumed
        ['demo_drop.json']
    """
    settings = settings or get_settings()
    folder = settings.live_feed_dir
    folder.mkdir(parents=True, exist_ok=True)
    report = DropFolderReport(folder=str(folder))
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in JSON_SUFFIXES | HTML_SUFFIXES:
            continue
        if time.time() - path.stat().st_mtime < STABLE_SECONDS:
            report.skipped.append(path.name)
            continue
        report.scanned += 1
        items = _parse_file(path, settings, budget, report)
        bucket = "consumed" if items else "quarantine"
        _move_aside(path, folder / bucket)
        (report.consumed if items else report.quarantined).append(path.name)
        report.opportunities.extend(items)
    logger.info(
        "drop folder %s: %d scanned, %d parsed, %d quarantined, %d waiting",
        folder,
        report.scanned,
        len(report.consumed),
        len(report.quarantined),
        len(report.skipped),
    )
    return report


def _parse_file(
    path: Path,
    settings: Settings,
    budget: RunBudget | None,
    report: DropFolderReport,
) -> list[Opportunity]:
    """Dispatch one dropped file: JSON is validated, HTML is extracted."""
    if path.suffix.lower() in JSON_SUFFIXES:
        return _parse_json(path, report)
    return _parse_html(path, settings, budget, report)


def _parse_json(path: Path, report: DropFolderReport) -> list[Opportunity]:
    """Validate a dropped JSON payload as opportunity record(s); no model."""
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        report.errors.append(f"{path.name}: unreadable JSON ({exc})")
        return []
    if isinstance(payload, dict):
        rows: Any = payload.get("opportunities", [payload])
    else:
        rows = payload
    if not isinstance(rows, list):
        report.errors.append(f"{path.name}: expected an object or a list of objects")
        return []
    return _validate_rows(rows, path.name, report)


def _validate_rows(rows: list[Any], file_name: str, report: DropFolderReport) -> list[Opportunity]:
    """Model-validate each row; a broken row is an error, never a crash."""
    items: list[Opportunity] = []
    for index, row in enumerate(rows, start=1):
        try:
            item = Opportunity.model_validate(row)
        except ValidationError as exc:
            report.errors.append(f"{file_name}#{index}: {exc.errors()[0]['msg']}")
            continue
        item.id = item.id or opportunity_id(item.title, item.url)
        item.added_via = "user"
        item.source = f"drop:{file_name}"
        items.append(item)
    return items


def _parse_html(
    path: Path,
    settings: Settings,
    budget: RunBudget | None,
    report: DropFolderReport,
) -> list[Opportunity]:
    """Clean the dropped page and extract it exactly like any other web page."""
    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.errors.append(f"{path.name}: unreadable HTML ({exc})")
        return []
    page = clean_html(html)
    outcome = extract_record(
        page.text,
        url=page.canonical,
        source_name=f"drop:{path.name}",
        title_hint=page.title,
        budget=budget,
        settings=settings,
    )
    if outcome.opportunity is None:
        why = outcome.rejected_reason or "no model answer (pending for the next cycle)"
        report.errors.append(f"{path.name}: {why}")
        return []
    item = outcome.opportunity
    item.added_via = "user"
    item.source = f"drop:{path.name}"
    return [item]


def _move_aside(path: Path, destination_dir: Path) -> Path:
    """Move a file into consumed/ or quarantine/ without ever deleting it."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / path.name
    counter = 1
    while target.exists():
        target = destination_dir / f"{path.stem}-{counter}{path.suffix}"
        counter += 1
    shutil.move(str(path), str(target))
    return target
