"""OpenAI-compatible chat completions adapter.

Works with any provider exposing POST {base_url}/chat/completions (OpenAI,
DeepSeek, Qwen/DashScope compatible mode, Moonshot, local gateways, ...).
Credentials stay server-side; requests ask for a JSON object and the caller
validates the parsed result against a Pydantic schema.
"""

import json
import time

import httpx
from pydantic import BaseModel

from app.ai.providers.base import LlmError, LlmResult, LlmUsage
from app.core.config import get_settings


class OpenAiCompatProvider:
    def complete_json(
        self, *, system: str, user: str, response_model: type[BaseModel]
    ) -> LlmResult:
        settings = get_settings()
        if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
            raise LlmError("LLM provider is not configured (base URL, API key, model).")

        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        system_prompt = (
            f"{system}\n\nRespond with a single JSON object that validates against this "
            f"JSON Schema. No markdown, no commentary.\n{schema_json}"
        )
        body = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            started = time.monotonic()
            try:
                response = httpx.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json=body,
                    timeout=settings.llm_timeout_seconds,
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                if response.status_code >= 500:
                    last_error = LlmError(f"Provider returned {response.status_code}.")
                    continue
                if response.status_code != 200:
                    raise LlmError(f"Provider returned {response.status_code}.")
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                content_json = json.loads(content)
                if not isinstance(content_json, dict):
                    raise LlmError("Provider response was not a JSON object.")
                usage = payload.get("usage", {})
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                cost = None
                if input_tokens is not None and output_tokens is not None:
                    cost = (
                        input_tokens / 1000 * settings.llm_input_cost_per_1k
                        + output_tokens / 1000 * settings.llm_output_cost_per_1k
                    )
                return LlmResult(
                    content_json=content_json,
                    usage=LlmUsage(
                        provider="openai_compat",
                        model_name=settings.llm_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                        estimated_cost=cost,
                    ),
                )
            except httpx.TimeoutException as exc:
                last_error = LlmError("Provider request timed out.", timeout=True)
                if attempt < settings.llm_max_retries:
                    continue
                raise last_error from exc
            except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
                raise LlmError(f"Provider request failed: {exc}") from exc
        raise last_error if last_error else LlmError("Provider request failed.")
