# EMBEDDING_PROVIDER=gemini, offline: a stand-in client replaces Google's API.
# Batching, normalization, the disk cache, empty texts, the live-call gate and
# the quota error are checked without any network call.

from types import SimpleNamespace

import numpy as np
import pytest

from oppradar_ai.config import Settings
from oppradar_ai.embeddings import Embedder, EmbeddingError


class FakeModels:
    def __init__(self, fail_with=None):
        self.calls = []
        self.fail_with = fail_with

    def embed_content(self, *, model, contents, config):
        self.calls.append((model, list(contents), config))
        if self.fail_with:
            raise self.fail_with
        # A different, non-normalized vector per text (length = text length).
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[float(len(t)), 1.0, 0.0, 2.0]) for t in contents]
        )


def gemini(tmp_path, models, **overrides):
    settings = Settings(
        embedding_provider="gemini",
        gemini_api_key="test-key",
        run_live_llm=True,
        gemini_embedding_dim=4,
        embedding_batch_size=2,
        data_dir=tmp_path,
        **overrides,
    )
    emb = Embedder(settings)
    types = SimpleNamespace(EmbedContentConfig=lambda **kw: kw)
    emb._model = (SimpleNamespace(models=models), types)  # skip the real client
    return emb


def test_vectors_are_batched_normalized_and_typed(tmp_path):
    models = FakeModels()
    emb = gemini(tmp_path, models)
    vectors = emb.encode(["python", "data science", "ai"])
    assert vectors.shape == (3, 4)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert [len(c[1]) for c in models.calls] == [2, 1]  # embedding_batch_size = 2
    model, _, config = models.calls[0]
    assert model == "gemini-embedding-001"
    assert config == {"task_type": "SEMANTIC_SIMILARITY", "output_dimensionality": 4}
    assert emb.dim == 4


def test_cached_texts_are_not_sent_again(tmp_path):
    models = FakeModels()
    gemini(tmp_path, models).encode(["python", "data"])
    fresh = gemini(tmp_path, models)  # new process: disk cache only
    fresh.encode(["python", "data", "ml"])
    assert [c[1] for c in models.calls] == [["python", "data"], ["ml"]]


def test_empty_text_is_a_zero_vector_without_a_call(tmp_path):
    models = FakeModels()
    vectors = gemini(tmp_path, models).encode(["", "python"])
    assert not vectors[0].any() and models.calls[0][1] == ["python"]


def test_quota_is_an_embedding_error_not_retried(tmp_path):
    error = Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
    error.code = 429
    models = FakeModels(fail_with=error)
    with pytest.raises(EmbeddingError, match="quota"):
        gemini(tmp_path, models).encode(["python"])
    assert len(models.calls) == 1


def test_live_gate_and_key_are_required(tmp_path):
    off = Embedder(Settings(embedding_provider="gemini", gemini_api_key="k", run_live_llm=False,
                            data_dir=tmp_path))  # fmt: skip
    with pytest.raises(EmbeddingError, match="RUN_LIVE_LLM"):
        off.encode(["python"])
    no_key = Embedder(Settings(embedding_provider="gemini", gemini_api_key="", run_live_llm=True,
                               data_dir=tmp_path))  # fmt: skip
    with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
        no_key.encode(["python"])
