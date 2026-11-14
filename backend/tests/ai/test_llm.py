"""Unit tests for the LLM abstraction (no database, no network)."""

import pytest

from app.ai import llm
from app.ai.providers.base import LlmError, LlmResult, LlmUsage
from app.ai.providers.mock import MockProvider, build_mock_instance
from app.ai.schemas import (
    DeepCheckResult,
    PolishResult,
    TeachingContent,
    TranslationResult,
    ValidationJudgement,
)
from app.core.config import get_settings
from app.core.exceptions import ApiError


@pytest.mark.parametrize(
    "model",
    [DeepCheckResult, TeachingContent, PolishResult, TranslationResult, ValidationJudgement],
)
def test_mock_provider_produces_schema_valid_output(model):
    instance = build_mock_instance(model, "He go to school yesterday.")
    assert isinstance(instance, model)
    dumped = instance.model_dump(mode="json")
    assert model.model_validate(dumped)


def test_call_llm_with_mock_returns_parsed_and_usage():
    parsed, usage = llm.call_llm(system="system", user="user text", response_model=TeachingContent)
    assert isinstance(parsed, TeachingContent)
    assert usage.provider == "mock"
    assert usage.estimated_cost == 0.0
    assert usage.latency_ms >= 0


def test_unknown_provider_maps_to_500(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "does-not-exist")
    with pytest.raises(ApiError) as exc:
        llm.call_llm(system="s", user="u", response_model=TeachingContent)
    assert exc.value.status_code == 500


def test_unconfigured_openai_compat_maps_to_502(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai_compat")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    with pytest.raises(ApiError) as exc:
        llm.call_llm(system="s", user="u", response_model=TeachingContent)
    assert exc.value.status_code == 502
    assert exc.value.code == "LLM_PROVIDER_ERROR"


def test_invalid_provider_output_maps_to_502(monkeypatch):
    class BadProvider:
        def complete_json(self, *, system, user, response_model):
            return LlmResult(
                content_json={"not": "valid"},
                usage=LlmUsage("bad", "bad", 1, 1, 1, 0.0),
            )

    monkeypatch.setattr(llm, "get_provider", lambda: BadProvider())
    with pytest.raises(ApiError) as exc:
        llm.call_llm(system="s", user="u", response_model=TeachingContent)
    assert exc.value.status_code == 502


def test_timeout_maps_to_504(monkeypatch):
    class TimeoutProvider:
        def complete_json(self, *, system, user, response_model):
            raise LlmError("timed out", timeout=True)

    monkeypatch.setattr(llm, "get_provider", lambda: TimeoutProvider())
    with pytest.raises(ApiError) as exc:
        llm.call_llm(system="s", user="u", response_model=TeachingContent)
    assert exc.value.status_code == 504
    assert exc.value.code == "LLM_TIMEOUT"


def test_mock_is_deterministic():
    provider = MockProvider()
    first = provider.complete_json(system="s", user="same input", response_model=DeepCheckResult)
    second = provider.complete_json(system="s", user="same input", response_model=DeepCheckResult)
    assert first.content_json == second.content_json
