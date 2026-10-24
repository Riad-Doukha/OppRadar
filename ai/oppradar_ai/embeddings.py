# Local text embeddings: sentence-transformers (free, runs on your machine) or a
# deterministic hashing encoder for tests and offline work. Called by:
# matching/ (profile vs opportunity similarity) and later chat/retrieval.
# No API key and no network at run time: the model comes from the local cache.

from __future__ import annotations

import hashlib
import logging
import re

import numpy as np

from oppradar_ai.config import Settings, get_settings
from oppradar_ai.llm import DiskCache

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Size of the hashing encoder's vector (EMBEDDING_PROVIDER=fake). An
# implementation detail of the offline encoder, not a user-facing setting.
_FAKE_DIM = 256


class EmbeddingError(RuntimeError):
    """No usable embedding model (package missing, model unavailable offline)."""


class Embedder:
    """Text -> L2-normalized vector, memoized in memory and (real models) on disk.

    Example:
        >>> emb = Embedder(provider="fake")
        >>> emb.encode(["python internship", "python internship"]).shape
        (2, 256)
        >>> float(emb.encode_one("python") @ emb.encode_one("python"))
        1.0
    """

    def __init__(self, settings: Settings | None = None, *, provider: str | None = None) -> None:
        settings = settings or get_settings()
        self.settings = settings
        self.provider = provider or settings.embedding_provider
        if self.provider == "sentence_transformers":
            self.model_id = settings.embedding_model
        else:
            self.model_id = f"hash-{_FAKE_DIM}"
        self._model = None
        self._dimension = 0
        self._memory: dict[str, np.ndarray] = {}
        self._disk_cache: DiskCache | None = None

    # -- public API ---------------------------------------------------------
    @property
    def dim(self) -> int:
        """Vector size of the configured model (loads it on first use)."""
        if self.provider == "fake":
            return _FAKE_DIM
        self._ensure_model()
        return self._dimension

    def encode(self, texts: list[str]) -> np.ndarray:
        """One L2-normalized row per text, cache hits first.

        Example:
            >>> Embedder(provider="fake").encode(["python", ""]).shape
            (2, 256)
        """
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)  # no rows: only zipped over
        if self.provider == "sentence_transformers":
            self._ensure_model()  # first: model_id (hence cache keys) must be final
        rows: list[np.ndarray | None] = [self._lookup(text) for text in texts]
        missing = [i for i, row in enumerate(rows) if row is None]
        batch = self.settings.embedding_batch_size
        for start in range(0, len(missing), batch):
            indexes = missing[start : start + batch]
            vectors = self._encode_batch([texts[i] for i in indexes])
            for i, vector in zip(indexes, vectors, strict=True):
                rows[i] = vector
                self._remember(texts[i], vector)
        return np.vstack([row for row in rows if row is not None])

    def encode_one(self, text: str) -> np.ndarray:
        """Vector of a single text (see `encode`)."""
        return self.encode([text])[0]

    # -- caching -------------------------------------------------------------
    def _key(self, text: str) -> str:
        return DiskCache.key(self.provider, self.model_id, text)

    def _lookup(self, text: str) -> np.ndarray | None:
        key = self._key(text)
        hit = self._memory.get(key)
        if hit is not None:
            return hit
        if self.provider == "fake":  # free to compute: never worth a disk file
            return None
        record = self._disk.get(key)
        if record is None:
            return None
        vector = np.asarray(record.get("vector"), dtype=np.float32)
        if vector.ndim != 1 or not vector.size:
            return None
        self._memory[key] = vector
        return vector

    def _remember(self, text: str, vector: np.ndarray) -> None:
        key = self._key(text)
        self._memory[key] = vector
        if self.provider != "fake":
            self._disk.put(key, {"model": self.model_id, "vector": vector.tolist()})

    @property
    def _disk(self) -> DiskCache:
        if self._disk_cache is None:
            self._disk_cache = DiskCache(self.settings.cache_dir / "embeddings")
        return self._disk_cache

    # -- model ---------------------------------------------------------------
    def _encode_batch(self, texts: list[str]) -> list[np.ndarray]:
        if self.provider == "fake":
            return [_normalize(_hash_encode(text, _FAKE_DIM)) for text in texts]
        model = self._ensure_model()
        raw = model.encode(
            list(texts),
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [row for row in _normalize(np.asarray(raw, dtype=np.float32))]

    def _ensure_model(self):
        """Load the primary model, falling back to `embedding_fallback_model`."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise EmbeddingError("sentence-transformers is not installed") from exc
        tried: list[str] = []
        names = (self.settings.embedding_model, self.settings.embedding_fallback_model)
        for candidate in dict.fromkeys(name for name in names if name):
            tried.append(candidate)
            try:
                model = SentenceTransformer(candidate)
            except Exception as exc:  # offline cache miss, unknown id, bad network
                logger.warning("embedding model %s unavailable (%s)", candidate, exc)
                continue
            self._model = model
            self.model_id = candidate
            self._dimension = _dimension_of(model)
            logger.info("loaded embedding model %s (dim=%d)", candidate, self._dimension)
            return model
        raise EmbeddingError(f"no embedding model available: {' | '.join(tried)}")


def _dimension_of(model) -> int:
    """Vector size of the model, read from a one-string probe.

    A probe instead of `get_sentence_embedding_dimension()`: that method was
    renamed mid-life (-> `get_embedding_dimension`) and warns on some versions.
    """
    return int(model.encode(["dimension probe"], show_progress_bar=False).shape[1])


def _normalize(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization; an all-zero row stays all-zero (no NaN)."""
    if matrix.ndim == 1:
        norm = float(np.linalg.norm(matrix))
        return matrix / norm if norm else matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


def _hash_encode(text: str, dim: int) -> np.ndarray:
    """Deterministic feature-hashing vector over unigrams + bigrams.

    Not a language model: it exists so tests and offline runs exercise the exact
    same code path (encode -> cosine -> score) without downloading anything.
    """
    vector = np.zeros(dim, dtype=np.float32)
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return vector  # empty text -> zero vector -> cosine() reports 0.0
    features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
    for feature in features:
        digest = hashlib.sha1(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % dim
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    return _normalize(vector)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors, 0.0 when either side is empty.

    Example:
        >>> round(cosine(np.array([1.0, 0.0]), np.array([1.0, 0.0])), 3)
        1.0
        >>> cosine(np.zeros(3), np.ones(3))
        0.0
    """
    left, right = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if not left or not right:
        return 0.0
    return float(np.dot(a, b) / (left * right))


def get_embedder(settings: Settings | None = None) -> Embedder:
    """The configured embedder, built once per (provider, model).

    Example:
        >>> get_embedder().provider in ("fake", "sentence_transformers")
        True
    """
    settings = settings or get_settings()
    key = f"emb-{settings.embedding_provider}|{settings.embedding_model}"
    if key not in _INSTANCES:
        _INSTANCES[key] = Embedder(settings)
    return _INSTANCES[key]


_INSTANCES: dict[str, Embedder] = {}
