"""Embedding unit tests (mock provider: determinism, dimensions, norms)."""

import math

from app.ai.embeddings import MockEmbeddingProvider, embed_texts
from app.core.config import get_settings


def test_mock_embeddings_deterministic():
    provider = MockEmbeddingProvider()
    first = provider.embed(["gain hands-on experience"])
    second = provider.embed(["gain hands-on experience"])
    assert first.vectors == second.vectors
    assert first.model_name == "mock-embedding-v1"


def test_mock_embeddings_dimension_and_norm():
    dim = get_settings().embedding_dimensions
    result = embed_texts(["hello world", "另一个表达"])
    assert len(result.vectors) == 2
    for vector in result.vectors:
        assert len(vector) == dim
        norm = math.sqrt(sum(x * x for x in vector))
        assert abs(norm - 1.0) < 1e-6


def test_different_texts_different_vectors():
    result = embed_texts(["alpha expression", "beta expression"])
    assert result.vectors[0] != result.vectors[1]
