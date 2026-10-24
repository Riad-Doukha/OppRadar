# sources.yaml provenance rules: verified + notes on every row, real
# http(s) URLs only, unique names, and clear errors for broken files.

from pathlib import Path

import pytest
import yaml

from oppradar_ai.ingestion.sources import load_sources

# The committed file (tests run with DATA_DIR pointed at a temp dir).
COMMITTED = Path(__file__).resolve().parents[1] / "data" / "sources.yaml"


def test_committed_sources_yaml_has_provenance() -> None:
    rows = yaml.safe_load(COMMITTED.read_text(encoding="utf-8"))["sources"]
    assert len(rows) >= 4
    for row in rows:
        assert {"name", "url", "kind", "verified", "notes"} <= set(row)
        assert isinstance(row["verified"], bool)
        assert row["notes"].strip()  # every source explains itself
        assert row["url"].startswith("https://")  # never invented/insecure URLs


def test_load_sources_returns_validated_models() -> None:
    sources = load_sources(COMMITTED)
    names = [s.name for s in sources]
    assert len(names) == len(set(names))
    assert {s.kind for s in sources} <= {"rss", "page", "search"}
    assert any(s.verified for s in sources)
    assert any(not s.verified for s in sources)  # unconfirmed ones stay listed
    assert any(not s.enabled for s in sources)  # ...but disabled


def test_missing_file_raises_a_clear_error() -> None:
    with pytest.raises(FileNotFoundError, match="sources file not found"):
        load_sources(Path("no_such_dir/sources.yaml"))


def test_row_without_notes_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n  - name: a\n    url: https://example.org/f\n"
        "    kind: rss\n    verified: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="notes"):
        load_sources(path)


def test_non_http_url_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n  - name: a\n    url: ftp://example.org/f\n"
        "    kind: rss\n    verified: false\n    notes: cannot confirm\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-http"):
        load_sources(path)


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - name: a\n    url: https://example.org/1\n    kind: rss\n"
        "    verified: true\n    notes: one\n"
        "  - name: a\n    url: https://example.org/2\n    kind: rss\n"
        "    verified: true\n    notes: two\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_sources(path)
