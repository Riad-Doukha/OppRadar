"""Remove the AI fixture opportunities (seeded by scripts/seed.py) before launch.

    cd backend
    python scripts/remove_fixtures.py           # list what would be deleted
    python scripts/remove_fixtures.py --apply   # delete them

Rows are found by the fixtures' external ids. Deleting cascades to their
matches, saves and applications (they point at fake opportunities).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oppradar_ai.config import get_settings as get_ai_settings  # noqa: E402

from app.services.db import get_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    args = parser.parse_args()

    raw = json.loads((get_ai_settings().fixtures_dir / "opportunities.json").read_text("utf-8"))
    ids = [item["id"] for item in raw]
    db = get_db()
    rows = db.table("opportunities").select("id, external_id, title").in_("external_id", ids)
    rows = rows.execute().data
    for r in rows:
        print(f"{r['external_id']:>8}  {r['title']}")
    if not rows:
        print("No fixture opportunities left.")
        return
    if not args.apply:
        print(f"\n{len(rows)} fixture opportunities. Run with --apply to delete them.")
        return
    db.table("opportunities").delete().in_("id", [r["id"] for r in rows]).execute()
    print(f"\nDeleted {len(rows)} fixture opportunities.")


if __name__ == "__main__":
    main()
