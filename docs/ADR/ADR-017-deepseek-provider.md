# ADR-017 — DeepSeek as Temporary Real LLM Provider

**Date:** 2026-11-15
**Status:** Accepted (user decision)

## Context

The product needs a real LLM for contextual teaching, expression improvement,
Chinese-to-English assistance, IELTS evaluation and rewriting. The user
supplied a temporary DeepSeek configuration and a locally rotated API key.

## Decision

- `LLM_PROVIDER=deepseek` with `LLM_BASE_URL=https://api.deepseek.com` and
  `LLM_MODEL=deepseek-flash` (as configured by the user; the model name is
  never substituted silently — connectivity verification reports mismatches).
- The DeepSeek adapter speaks OpenAI-compatible chat completions at
  `{base}/chat/completions`; when `LLM_BASE_URL` ends with `/anthropic` it
  speaks the Anthropic-compatible messages API at `{base}/v1/messages`.
- Credentials are read exclusively from environment configuration (`.env`,
  gitignored). No credentials in code, frontend, logs or commits. The key
  exposed in the chat attachment was NOT used; the user places the newly
  rotated key locally.
- The deterministic MockProvider remains the provider for ALL automated tests
  (pytest forces `LLM_PROVIDER=mock`; the E2E backend env sets it too). Real
  and mock providers are strictly separated; mock outputs are never evidence
  of real linguistic quality.
- Every real call records provider, model, prompt version, input/output
  tokens (when exposed), latency and estimated cost in `ai_usage_logs`.
  Usage metadata is read defensively — providers differ.
- Timeouts map to 504 `LLM_TIMEOUT`; provider failures to 502
  `LLM_PROVIDER_ERROR`; 4xx errors are not retried and never fall back to
  another model. 5xx/timeouts retry up to `LLM_MAX_RETRIES`.
- No services are purchased and no paid subscriptions activated.

## Verification

- `backend/scripts/verify_llm.py` checks connectivity, structured output,
  usage reporting and model-name consistency (never prints the key).
- `backend/scripts/eval_ai.py` runs representative evaluation datasets
  against the real provider and records quality metrics + cost; extended as
  expression/evaluation/rewrite services land (Slices 4/7).

## Consequences

- Real AI linguistic-quality verification is pending until the rotated key
  is placed in `.env` (reported to the user as the single open item).
- Cost estimates require configured per-1K pricing (`LLM_INPUT_COST_PER_1K`,
  `LLM_OUTPUT_COST_PER_1K`); default 0 until verified pricing is set.
