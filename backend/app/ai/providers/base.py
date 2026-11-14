"""Provider interface and shared usage types."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class LlmUsage:
    provider: str
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    estimated_cost: float | None


@dataclass(frozen=True)
class LlmResult:
    content_json: dict
    usage: LlmUsage


class LlmProvider(Protocol):
    def complete_json(
        self, *, system: str, user: str, response_model: type[BaseModel]
    ) -> LlmResult:
        """Return a JSON object conforming to response_model. Raises LlmError."""
        ...


class LlmError(Exception):
    """Provider failure mapped to LLM_PROVIDER_ERROR / LLM_TIMEOUT upstream."""

    def __init__(self, message: str, *, timeout: bool = False) -> None:
        super().__init__(message)
        self.timeout = timeout
