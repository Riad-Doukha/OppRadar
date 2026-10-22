# Freeze 20 current REAL RSS entries (round-robin across the enabled feeds in
# sources.yaml) into data/eval/live_snapshot.json, plus a hand-labeling
# template. Public web data only — no personal data ever touches these files.
#
# Usage:  python scripts/snapshot_live.py [--count 20]
# Then:   copy live_labels.template.json -> live_labels.json and fill it by hand.

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from oppradar_ai.config import get_settings, setup_logging
from oppradar_ai.ingestion.fetch import PageFetcher
from oppradar_ai.ingestion.rss import read_feed
from oppradar_ai.ingestion.sources import load_sources

logger = logging.getLogger("snapshot_live")


def _round_robin(feeds: dict[str, list], count: int) -> list[tuple[str, object]]:
    """Interleave entries across feeds so one source never dominates."""
    picked: list[tuple[str, object]] = []
    order = list(feeds)
    index = 0
    while len(picked) < count:
        progressed = False
        for name in order:
            rows = feeds[name]
            if index < len(rows) and len(picked) < count:
                picked.append((name, rows[index]))
                progressed = True
        if not progressed:
            break
        index += 1
    return picked


def _entry(source: str, item, eid: str, fetched_at: str) -> dict:
    return {
        "id": eid,
        "source": source,
        "title": item.title.strip(),
        "url": item.url.strip(),
        "summary": item.summary.strip(),
        "published": item.published.isoformat() if item.published else None,
        "fetched_at": fetched_at,
    }


def _write_template(path: Path, ids: list[str]) -> None:
    if path.exists():
        return
    template = {
        eid: {"is_opportunity": None, "deadline": None, "type": None}
        for eid in ids
    }
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    logger.info("wrote label template %s", path)


def snapshot(count: int = 20, out: Path | None = None) -> Path:
    settings = get_settings().ensure_dirs()
    out = out or (settings.eval_dir / "live_snapshot.json")
    fetcher = PageFetcher(settings)
    fetched_at = datetime.now(timezone.utc).isoformat()

    feeds: dict[str, list] = {}
    for source in load_sources(settings.sources_path):
        if not (source.enabled and source.kind == "rss"):
            continue
        entries, errors = read_feed(source.url, fetcher)
        if errors:
            logger.warning("%s: %s", source.name, "; ".join(errors))
        if entries:
            feeds[source.name] = entries
    if not feeds:
        raise SystemExit("no RSS entries fetched — check network and sources.yaml")

    picked = _round_robin(feeds, count)
    rows = [
        _entry(name, item, f"e{i + 1:02d}", fetched_at)
        for i, (name, item) in enumerate(picked)
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"count": len(rows), "entries": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_template(out.with_name("live_labels.template.json"), [r["id"] for r in rows])
    logger.info("froze %d entries -> %s", len(rows), out)
    return out


if __name__ == "__main__":
    setup_logging("INFO")
    parser = argparse.ArgumentParser(description="Freeze real RSS entries for hand labeling.")
    parser.add_argument("--count", type=int, default=20, help="entries to freeze (default 20)")
    parser.add_argument("--out", type=Path, default=None, help="output JSON path")
    args = parser.parse_args()
    snapshot(args.count, args.out)
