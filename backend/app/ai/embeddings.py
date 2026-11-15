"""Embedding provider abstraction (SD §8, ERD §9.3).

Embeddings are rebuildable data: the stored model name + content hash let a
re-embedding job detect stale vectors. The mock provider produces deterministic
pseudo-vectors for automated tests ONLY — they carry no semantic meaning; real
semantic quality requires a configured embedding endpoint.
"""

import hashlib
import math
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import ApiError


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model_name: str
    provider: str


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> EmbeddingResult: ...


class MockEmbeddingProvider:
    """Deterministic unit-norm pseudo-vectors (tests only, not semantic)."""

    def embed(self, texts: list[str]) -> EmbeddingResult:
        settings = get_settings()
        dim = settings.embedding_dimensions
        vectors = []
        for text in texts:
            seed = hashlib.sha256(text.encode("utf-8")).digest()
            raw = [((seed[i % len(seed)] + i * 37) % 256) / 255.0 - 0.5 for i in range(dim)]
            norm = math.sqrt(sum(x * x for x in raw)) or 1.0
            vectors.append([x / norm for x in raw])
        return EmbeddingResult(vectors=vectors, model_name="mock-embedding-v1", provider="mock")


class OpenAiCompatEmbeddingProvider:
    def embed(self, texts: list[str]) -> EmbeddingResult:
        settings = get_settings()
        if (
            not settings.embedding_base_url
            or not settings.embedding_api_key
            or not settings.embedding_model
        ):
            raise ApiError(503, "LLM_PROVIDER_ERROR", "Embedding provider is not configured.")
        try:
            response = httpx.post(
                f"{settings.embedding_base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.embedding_model, "input": texts},
                timeout=settings.embedding_timeout_seconds,
            )
            if response.status_code != 200:
                raise ApiError(
                    502,
                    "LLM_PROVIDER_ERROR",
                    f"Embedding provider returned {response.status_code}.",
                )
            payload = response.json()
            ordered = sorted(payload["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            raise ApiError(502, "LLM_PROVIDER_ERROR", "Embedding request failed.") from exc
        for vector in vectors:
            if len(vector) != settings.embedding_dimensions:
                raise ApiError(
                    502,
                    "LLM_PROVIDER_ERROR",
                    "Embedding dimensions do not match the configured vector column.",
                )
        return EmbeddingResult(
            vectors=vectors,
            model_name=payload.get("model", settings.embedding_model),
            provider="openai_compat",
        )


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider()
    if settings.embedding_provider == "openai_compat":
        return OpenAiCompatEmbeddingProvider()
    raise ApiError(
        500, "LLM_PROVIDER_ERROR", f"Unknown embedding provider: {settings.embedding_provider}"
    )


def embed_texts(texts: list[str]) -> EmbeddingResult:
    return get_embedding_provider().embed(texts)
