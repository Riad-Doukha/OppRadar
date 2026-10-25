"""Write the API's OpenAPI schema to a file (the frontend generates its types from it).

python scripts/export_openapi.py ../frontend/lib/api/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    target.write_text(json.dumps(app.openapi(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(app.openapi()['paths'])} paths)")
