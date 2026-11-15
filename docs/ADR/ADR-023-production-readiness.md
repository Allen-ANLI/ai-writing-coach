# ADR-023: Production Readiness — Observability, Hardening, Deployment

**Status:** Accepted (Slice 11b, 2026-11-15)
**Related:** Directive §I, DEPLOYMENT.md, BACKUP_RECOVERY.md, SECURITY_REVIEW.md,
PERFORMANCE_REPORT.md, LAUNCH_CHECKLIST.md.

## Context

The product must be production-ready: deployable, observable, recoverable,
hardened, and verified — without activating paid services or deploying
publicly (both user-gated).

## Decision

1. **Observability.** Structured JSON access logs with a per-request
   `X-Request-ID` (echoed from caller or generated), method/path/status/
   duration_ms. Bodies, tokens, cookies and keys are never logged. Health
   checks log at DEBUG. AI usage stays in `ai_usage_logs` (ADR-019).
2. **Hardening.** A general per-IP sliding-window API rate limit (default
   300/min, configurable, 0 disables) complements the stricter auth limiter.
   Both are in-process and isolated behind a single storage point so a shared
   store can replace them for multi-worker deployments. nginx adds security
   headers; CORS stays an explicit whitelist.
3. **Deployment.** Multi-stage non-root Dockerfiles (backend runs migrations
   on start), a production compose stack exposing only nginx, and a complete
   `.env.production.example` with CHANGE_ME markers. Single-worker assumption
   is documented with a concrete scaling path.
4. **Recovery.** `pg_dump -Fc` backup / `pg_restore` scripts; restore refuses
   the live DB without `--force`; a verification script proves round-trip
   integrity (40 tables, identical counts) using a self-created scratch DB.
5. **CI.** GitHub Actions: backend (ruff + pytest with Postgres/LT services +
   pip-audit), frontend (eslint/tsc/vitest/build + `npm audit --omit=dev`),
   E2E (chromium via PLAYWRIGHT_CHANNEL override; local dev keeps Edge).
6. **Verification artifacts.** Performance probe (re-verified 2026-11-15:
   worst P95 60.1 ms < 500 ms target, 30 samples/endpoint), security review
   (pip-audit clean; npm production audit clean; 8 moderate dev-only lint
   advisories accepted and documented), backup round-trip re-verified
   (40 tables), AI-quality harness report (real quality pending the user's
   key), and a launch checklist that keeps every paid/public action
   user-gated. `.dockerignore` files keep secrets and build artifacts out of
   Docker images.

## Consequences

- The stack is config-complete and reproducible; actual public deployment
  waits for explicit approval.
- Single-worker rate limiting/background tasks are a known, documented
  limitation with a migration path — not a hidden assumption.
- Console email / mock LLM / sandbox payments remain the safe defaults until
  the user activates real providers (launch blockers).
