# ADR-019: Evaluation Processing — In-Process Background Tasks, Server-Computed Bands

**Status:** Accepted (Slice 7, 2026-11-15)
**Related:** ERD §8, API Spec §13, ADR-016 (post-writing actions), ADR-017 (providers).

## Context

Evaluations and rewrites are long-running LLM operations. The contract returns
202 with a status lifecycle (queued → processing → completed/failed). The stack
is a modular monolith without a worker queue (no Celery/Redis), and tests must
stay deterministic and isolated from the dev database.

## Decision

1. **In-process background execution.** Queue endpoints persist a `queued` row
   and schedule a FastAPI `BackgroundTasks` job. The job opens its own session
   from `app.state.session_factory` (set to `SessionLocal` in `create_app`,
   overridden with the isolated test factory in `pg_fixtures`). The LLM call
   runs outside any DB transaction; results are persisted in a short
   transaction afterwards. A dedicated worker queue can replace this later
   without API changes — the status lifecycle is already the contract.
2. **Server-computed bands.** The LLM proposes per-criterion bands; the server
   normalizes each to half-band steps (round-half-up) and computes the overall
   band as the normalized mean. The LLM never decides the overall band.
   `is_estimate` is always true for AI results and surfaced in the UI as an
   "AI estimate" badge — never presented as an official IELTS score.
3. **Distinct schemas per task.** Task 1 uses `task_achievement`, Task 2 uses
   `task_response` (API Spec §13); general evaluation uses
   content/organization/language. All outputs are Pydantic-validated before
   touching user data; failures mark the row `failed` with an error message
   and log usage with status `error`.
4. **Immutable binding.** Evaluations reference a version of the same essay
   via composite FK; the UI creates a "Pre-evaluation" checkpoint first.
   Rewrites inherit `source_version_id = evaluation.version_id` (enforced by a
   composite FK). Acceptance is atomic: revision check → working document
   update → `ai_rewrite` version → `result_version_id` → `accept_rewrite`
   edit event. The client never supplies replacement content; the Original
   snapshot is never overwritten.
5. **Deletion semantics.** Deleting an evaluation cascades its rewrites
   (derived artifacts) but keeps created versions and edit events
   (`rewrite_id` SET NULL) — history stays auditable.

## Consequences

- No new infrastructure; horizontal scaling later requires moving background
  jobs to a shared worker (the queued-row protocol already supports it).
- Under TestClient, background jobs run synchronously, so integration tests
  observe completed results immediately; E2E polls the status endpoint.
- Band quality depends on the real provider; mock outputs verify the pipeline
  only (real-quality evaluation awaits the user's DeepSeek key, ADR-017).
