"""Shared test fixtures — paths to the synthetic data, no network needed."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from oppradar_ai.schemas import Opportunity, Profile

DATA_DIR = Path(__file__).parent.parent / "data"
FIXTURES_PATH = DATA_DIR / "fixtures" / "opportunities.json"
PROFILES_DIR = DATA_DIR / "eval" / "profiles"


@pytest.fixture(scope="session")
def fixture_opportunities() -> list[Opportunity]:
    rows = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return [Opportunity.model_validate(row) for row in rows]


@pytest.fixture(scope="session")
def synthetic_profiles() -> dict[str, Profile]:
    profiles = {}
    for path in sorted(PROFILES_DIR.glob("*.json")):
        profile = Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        profiles[profile.id or path.stem] = profile
    return profiles


@pytest.fixture
def fake_embed():
    """Deterministic hash-based embedding — keeps tests offline and reproducible."""

    def _embed(texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            vectors.append(rng.standard_normal(16).astype(np.float32))
        return np.stack(vectors) if vectors else np.zeros((0, 16), dtype=np.float32)

    return _embed
