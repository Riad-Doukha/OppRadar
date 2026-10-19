"""Embeddings for semantic matching.

Two interchangeable backends:
- "remote" (default): the shared LLM client's /embeddings endpoint.
- "local": sentence-transformers (pip install -e ".[embeddings]"), no API cost.

Choose with EMBEDDING_BACKEND=remote|local. Everything is injectable so tests
never need a network.
"""

from __future__ import annotations

import os

import numpy as np

from oppradar_ai import llm
from oppradar_ai.schemas import Opportunity, Profile

DEFAULT_BACKEND = os.getenv("EMBEDDING_BACKEND", "remote")


def opportunity_text(opportunity: Opportunity) -> str:
    """Flatten an opportunity into one embeddable string."""
    parts = [
        opportunity.title,
        opportunity.organization,
        opportunity.type.value,
        opportunity.description,
        " ".join(opportunity.tags),
        opportunity.location or "",
    ]
    return "\n".join(p for p in parts if p).strip()


def profile_text(profile: Profile) -> str:
    """Flatten a profile into one embeddable string (the 'query')."""
    parts = [
        profile.headline,
        profile.summary,
        "skills: " + ", ".join(profile.skills),
        "interests: " + ", ".join(profile.interests),
        "looking for: " + ", ".join(t.value for t in profile.preferences.types),
    ]
    return "\n".join(p for p in parts if p and not p.endswith(": ")).strip()


def _local_embed(texts: list[str]) -> np.ndarray:  # pragma: no cover - heavy optional dep
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    return np.asarray(model.encode(texts, normalize_embeddings=True), dtype=np.float32)


def embed_texts(texts: list[str], *, backend: str | None = None) -> np.ndarray:
    """Embed texts into an (n, d) float32 matrix. Empty input → (0, d)-ish array."""
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    backend = backend or DEFAULT_BACKEND
    if backend == "local":
        return _local_embed(texts)

    vectors = llm.embed(texts)
    return np.asarray(vectors, dtype=np.float32)


def cosine_similarity_matrix(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity between a (1, d) query and (n, d) corpus.

    Accepts 1-D vectors too (treated as single rows). Handles zero vectors
    (similarity 0) instead of producing NaN.
    """
    query = np.atleast_2d(query)
    corpus = np.atleast_2d(corpus)
    if corpus.shape[0] == 0 or query.size == 0 or corpus.size == 0:
        return np.zeros((corpus.shape[0],), dtype=np.float32)
    query = query.reshape(1, -1)
    q_norm = np.linalg.norm(query, axis=1, keepdims=True)
    c_norm = np.linalg.norm(corpus, axis=1, keepdims=True)
    denominator = np.where(q_norm * c_norm == 0, 1.0, q_norm * c_norm)
    return (query @ corpus.T).ravel() / denominator.ravel()


def skill_overlap(profile: Profile, opportunity: Opportunity) -> tuple[float, list[str]]:
    """Fraction of the opportunity's requested tags the user has (and vice versa).

    Returns (score in 0..1, matched skill names).
    """
    user_skills = {s.strip().lower() for s in profile.skills if s.strip()}
    requested = {t.strip().lower() for t in opportunity.tags if t.strip()}
    if not user_skills or not requested:
        return 0.0, []
    matched = sorted(user_skills & requested)
    score = len(matched) / len(requested)
    return round(min(score, 1.0), 3), matched
