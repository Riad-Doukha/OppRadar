"""Vector retrieval over opportunities.

A deliberately small index: embed once at build time, cosine-rank per query.
Persists to a single .npz so the backend can rebuild it cheaply on startup.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from oppradar_ai.matching import embeddings as emb
from oppradar_ai.schemas import Opportunity, Profile

DEFAULT_K = 5


class OpportunityIndex:
    """Embedding index over a list of opportunities."""

    def __init__(self, opportunities: list[Opportunity], embed_fn=None):
        self.opportunities = opportunities
        self._embed_fn = embed_fn or emb.embed_texts
        self._vectors: np.ndarray | None = None

    # -- building ---------------------------------------------------------- #
    def build(self) -> "OpportunityIndex":
        """Embed every opportunity (call once, then search many)."""
        if self.opportunities:
            self._vectors = self._embed_fn([emb.opportunity_text(o) for o in self.opportunities])
        else:
            self._vectors = np.zeros((0, 0), dtype=np.float32)
        return self

    @property
    def is_built(self) -> bool:
        return self._vectors is not None

    # -- searching --------------------------------------------------------- #
    def search(
        self,
        query: str,
        *,
        k: int = DEFAULT_K,
        profile: Profile | None = None,
    ) -> list[tuple[Opportunity, float]]:
        """Top-k opportunities for a query, most relevant first.

        When a profile is given, the query is blended with the profile text so
        results skew toward what the user actually qualifies for.
        """
        if not self.is_built:
            self.build()
        if not self.opportunities or self._vectors is None or not query.strip():
            return []

        blended = query.strip()
        if profile is not None:
            profile_blob = emb.profile_text(profile)
            if profile_blob:
                blended = f"{blended}\n{profile_blob}"

        query_vector = self._embed_fn([blended])[0]
        scores = emb.cosine_similarity_matrix(query_vector, self._vectors)
        order = np.argsort(scores)[::-1][: max(k, 0)]
        return [(self.opportunities[i], float(scores[i])) for i in order]

    # -- persistence ------------------------------------------------------- #
    def save(self, path: str | Path) -> None:
        """Persist vectors alongside the opportunities (npz bundle)."""
        if not self.is_built:
            self.build()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vectors": np.asarray(self._vectors, dtype=np.float32),
            "opportunities": np.array(
                [o.model_dump_json() for o in self.opportunities], dtype=object
            ),
        }
        np.savez_compressed(path, **payload)

    @classmethod
    def load(cls, path: str | Path, embed_fn=None) -> "OpportunityIndex":
        data = np.load(path, allow_pickle=True)
        opportunities = [Opportunity.model_validate_json(s) for s in data["opportunities"]]
        index = cls(opportunities, embed_fn=embed_fn)
        index._vectors = np.asarray(data["vectors"], dtype=np.float32)
        return index
