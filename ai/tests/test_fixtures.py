# Tests for the data scripts' output (the pre-Phase-2 fixes): 32 fixtures with
# 2 labelled scams + 2 borderline legit offers, typo/fictional-name fixes,
# the scam_labels eval set, the staleness stamp and the example-user CV URL.

import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from oppradar_ai.documents.reader import read_document
from oppradar_ai.schemas import Opportunity

AI_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = AI_ROOT / "data" / "fixtures"
EVAL = AI_ROOT / "data" / "eval"
SAMPLES = AI_ROOT / "data" / "samples"


def _load(name: str, folder: Path):
    return json.loads((folder / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def opportunities() -> list[dict]:
    return _load("opportunities.json", FIXTURES)


@pytest.fixture(scope="module")
def labels() -> dict[str, bool]:
    return _load("scam_labels.json", EVAL)


@pytest.fixture(scope="module")
def make_fixtures():
    """The generator script, imported so its helpers/constants can be checked."""
    spec = importlib.util.spec_from_file_location(
        "make_fixtures", AI_ROOT / "scripts" / "make_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_thirty_two_opportunities(opportunities) -> None:
    assert len(opportunities) == 32


def test_ids_are_unique_and_sequential(opportunities) -> None:
    ids = [o["id"] for o in opportunities]
    assert ids == [f"opp-{i:02d}" for i in range(1, 33)]


def test_labels_cover_every_id(opportunities, labels) -> None:
    assert set(labels) == {o["id"] for o in opportunities}
    assert all(isinstance(v, bool) for v in labels.values())


def test_exactly_two_known_scams(opportunities, labels) -> None:
    scam_ids = sorted(k for k, v in labels.items() if v)
    assert scam_ids == ["opp-31", "opp-32"]
    by_id = {o["id"]: o for o in opportunities}
    assert "URGENT" in by_id["opp-31"]["title"].upper()
    assert "registration fee" in by_id["opp-31"]["summary"]
    assert "bank details" in by_id["opp-32"]["summary"]


def test_borderline_fee_event_is_labelled_legit(opportunities, labels) -> None:
    event = next(o for o in opportunities if "registration fee" in o["summary"])
    assert event["title"] == "Algiers AI Summit Hackathon"
    assert labels[event["id"]] is False


def test_borderline_free_email_offer_is_labelled_legit(opportunities, labels) -> None:
    offer = next(
        o for o in opportunities if "@gmail.com" in o["summary"] and labels[o["id"]] is False
    )
    assert offer["title"] == "Junior Web Developer (Small Studio)"
    assert "No application fee" in offer["summary"]


def test_all_fixtures_schema_valid_and_one_expired(opportunities) -> None:
    models = [Opportunity.model_validate(o) for o in opportunities]
    assert sum(1 for m in models if m.is_expired) == 1


def test_opp28_typo_fixed(opportunities) -> None:
    opp = next(o for o in opportunities if o["id"] == "opp-28")
    assert "6 mois" in opp["summary"]


def test_opp05_organizer_is_fictional(opportunities) -> None:
    opp = next(o for o in opportunities if o["id"] == "opp-05")
    assert opp["organizer"] == "Acme Cloud Labs"
    assert all(o["organizer"] != "Sarawak" for o in opportunities)


def test_sample_cv_uses_example_user_url() -> None:
    truth = _load("cv_amine.json", SAMPLES / "ground_truth")
    urls = [p["url"] for p in truth["projects"]]
    assert any("github.com/example-user/" in u for u in urls)
    assert "example-user" in read_document(SAMPLES / "cv_amine.pdf").text


def test_stamp_exists_and_parses() -> None:
    stamp = (FIXTURES / "generated_on.txt").read_text(encoding="utf-8").strip()
    date.fromisoformat(stamp)


def test_warn_if_stale_false_when_generated_today(tmp_path, capsys, make_fixtures) -> None:
    stamp = tmp_path / "generated_on.txt"
    stamp.write_text("2026-01-01\n", encoding="utf-8")
    assert make_fixtures.warn_if_stale(stamp, today=date(2026, 1, 1)) is False
    assert capsys.readouterr().out == ""


def test_warn_if_stale_true_and_warns_when_old(tmp_path, capsys, make_fixtures) -> None:
    stamp = tmp_path / "generated_on.txt"
    stamp.write_text((date(2026, 1, 1) - timedelta(days=1)).isoformat(), encoding="utf-8")
    assert make_fixtures.warn_if_stale(stamp, today=date(2026, 1, 1)) is True
    out = capsys.readouterr().out
    assert "WARNING" in out and "make_fixtures.py" in out


def test_script_labels_match_eval_file(opportunities, labels, make_fixtures) -> None:
    assert {"opp-31", "opp-32"} == make_fixtures.KNOWN_SCAMS
    assert make_fixtures.make_scam_labels(opportunities) == labels
