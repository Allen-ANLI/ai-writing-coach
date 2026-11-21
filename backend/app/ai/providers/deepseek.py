"""DeepSeek provider (temporary real LLM provider per user decision 2026-11-15).

- OpenAI-compatible chat completions at {LLM_BASE_URL}/chat/completions.
- Anthropic-compatible messages API when LLM_BASE_URL ends with /anthropic.
- Credentials come exclusively from environment configuration; never logged.
- Model name is taken from LLM_MODEL as configured — never substituted silently.
- Usage metadata is read defensively: providers differ in what they expose.
- Cost is an estimate from configured per-1K pricing (0 when unconfigured).

The deterministic MockProvider remains the provider for automated tests;
real-provider behavior is verified by scripts/verify_llm.py and the AI
evaluation harness, never by swapping mocks into production paths.
"""

import json
import time

import httpx
from pydantic import BaseModel

from app.ai.providers.base import LlmError, LlmResult, LlmUsage
from app.core.config import get_settings


class DeepSeekProvider:
    def complete_json(
        self, *, system: str, user: str, response_model: type[BaseModel]
    ) -> LlmResult:
        settings = get_settings()
        if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
            raise LlmError(
                "DeepSeek is not configured: set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL."
            )
        if settings.llm_base_url.rstrip("/").endswith("/anthropic"):
            return self._anthropic(system, user, response_model)
        return self._openai_compat(system, user, response_model)

    def _schema_instruction(self, response_model: type[BaseModel]) -> str:
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        return (
            "Respond with a single JSON object that validates against this JSON Schema. "
            f"No markdown, no commentary.\n{schema_json}"
        )

    def _parse_content(self, content: str) -> dict:
        try:
            content_json = json.loads(content)
        except ValueError as exc:
            raise LlmError("Provider response was not valid JSON.") from exc
        if not isinstance(content_json, dict):
            raise LlmError("Provider response was not a JSON object.")
        return content_json

    def _usage(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        latency_ms: int,
        model_name: str,
    ) -> LlmUsage:
        settings = get_settings()
        cost = None
        if input_tokens is not None and output_tokens is not None:
            cost = (
                input_tokens / 1000 * settings.llm_input_cost_per_1k
                + output_tokens / 1000 * settings.llm_output_cost_per_1k
            )
        return LlmUsage(
            provider="deepseek",
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost,
        )

    def _openai_compat(self, system: str, user: str, response_model: type[BaseModel]) -> LlmResult:
        settings = get_settings()
        system_prompt = f"{system}\n\n{self._schema_instruction(response_model)}"
        body = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        last_error: LlmError | None = None
        for attempt in range(settings.llm_max_retries + 1):
            started = time.monotonic()
            try:
                response = httpx.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json=body,
                    timeout=settings.llm_timeout_seconds,
                    # Domestic API: never route through a system proxy (httpx
                    # reads the Windows registry proxy, which may be configured
                    # but not running — requests then fail with WinError 10061).
                    trust_env=False,
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                if response.status_code >= 500:
                    last_error = LlmError(f"DeepSeek returned {response.status_code}.")
                    continue
                if response.status_code != 200:
                    # 4xx (auth, unknown model, quota) is not retryable and must
                    # surface honestly — never fall back to another model.
                    raise LlmError(
                        f"DeepSeek returned {response.status_code}: {response.text[:200]}"
                    )
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                usage = payload.get("usage") or {}
                return LlmResult(
                    content_json=self._parse_content(content),
                    usage=self._usage(
                        input_tokens=usage.get("prompt_tokens"),
                        output_tokens=usage.get("completion_tokens"),
                        latency_ms=latency_ms,
                        model_name=payload.get("model", settings.llm_model),
                    ),
                )
            except httpx.TimeoutException as exc:
                last_error = LlmError("DeepSeek request timed out.", timeout=True)
                if attempt < settings.llm_max_retries:
                    continue
                raise last_error from exc
            except (httpx.HTTPError, KeyError, IndexError) as exc:
                raise LlmError(f"DeepSeek request failed: {exc}") from exc
        raise last_error if last_error else LlmError("DeepSeek request failed.")

    def _anthropic(self, system: str, user: str, response_model: type[BaseModel]) -> LlmResult:
        settings = get_settings()
        system_prompt = f"{system}\n\n{self._schema_instruction(response_model)}"
        body = {
            "model": settings.llm_model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user}],
        }
        last_error: LlmError | None = None
        for attempt in range(settings.llm_max_retries + 1):
            started = time.monotonic()
            try:
                response = httpx.post(
                    f"{settings.llm_base_url.rstrip('/')}/v1/messages",
                    headers={
                        "x-api-key": settings.llm_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json=body,
                    timeout=settings.llm_timeout_seconds,
                    trust_env=False,
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                if response.status_code >= 500:
                    last_error = LlmError(f"DeepSeek returned {response.status_code}.")
                    continue
                if response.status_code != 200:
                    raise LlmError(
                        f"DeepSeek returned {response.status_code}: {response.text[:200]}"
                    )
                payload = response.json()
                content = "".join(
                    block.get("text", "")
                    for block in payload.get("content", [])
                    if block.get("type") == "text"
                )
                usage = payload.get("usage") or {}
                return LlmResult(
                    content_json=self._parse_content(content),
                    usage=self._usage(
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                        latency_ms=latency_ms,
                        model_name=payload.get("model", settings.llm_model),
                    ),
                )
            except httpx.TimeoutException as exc:
                last_error = LlmError("DeepSeek request timed out.", timeout=True)
                if attempt < settings.llm_max_retries:
                    continue
                raise last_error from exc
            except (httpx.HTTPError, KeyError, IndexError) as exc:
                raise LlmError(f"DeepSeek request failed: {exc}") from exc
        raise last_error if last_error else LlmError("DeepSeek request failed.")
