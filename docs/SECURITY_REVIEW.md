# Security Review

**Status:** Slice 11b (2026-11-15). Review of the implemented system; items
marked ✅ are verified by automated tests or configuration, ⚠️ are operational
requirements for launch.

## Authentication & sessions
- ✅ Argon2 password hashing; timing-parity decoy hash for unknown emails.
- ✅ Short-lived JWT access tokens (15 min) + rotating HttpOnly/Secure/
  SameSite=Strict refresh cookies; refresh reuse revokes the token family and
  session (tested: `tests/auth/test_refresh.py`, `test_security.py`).
- ✅ Password reset: hashed single-use 60-min tokens, no account enumeration,
  all sessions revoked on confirm, rate-limited (ADR-022).
- ⚠️ `JWT_SECRET` must be a long random value in production (template enforces
  a CHANGE_ME marker; the built-in default is dev-only).

## Authorization & data isolation
- ✅ Every private query is user-scoped from the auth context; composite
  same-owner FKs across essays/expressions/evaluations/outlines/tasks.
- ✅ IELTS bank exposes only published + licensed rows; license gate in the
  repository layer (ADR-018).
- ✅ Account deletion/export are authenticated self-service; export never
  includes password hashes or refresh tokens (tested).

## Input handling & injection
- ✅ SQLAlchemy ORM / bound parameters throughout; no string-built SQL.
- ✅ Pydantic validation on every request body; LLM outputs validated against
  strict schemas before touching user data (`extra="forbid"`).
- ✅ TipTap document validation + codepoint-offset bounds checking.

## Transport & headers
- ✅ CORS is an explicit origin whitelist with credentials; methods/headers
  restricted to the contract surface.
- ✅ nginx adds X-Content-Type-Options, X-Frame-Options, Referrer-Policy.
- ⚠️ TLS must terminate upstream of nginx in production (HTTPS origin).

## Rate limiting & abuse
- ✅ Auth endpoints: strict per-IP sliding window.
- ✅ General API: per-IP sliding window (default 300/min, configurable).
- ⚠️ In-process limiter is single-worker; move to a shared store before
  horizontal scaling (DEPLOYMENT.md).

## Secrets & dependencies
- ✅ `.env` gitignored; `.env.example` / `.env.production.example` carry no
  real secrets; the exposed chat credential was never used (user directive).
- ✅ `.dockerignore` for backend and frontend keeps `.env*`, `node_modules`,
  `.next`, caches and tests out of Docker build contexts/images.
- ✅ LLM/embedding/email/payment providers are config-gated; mock/sandbox/
  console defaults never spend money or send real email.
- ✅ `pip-audit` (2026-11-15): **no known vulnerabilities** in application
  dependencies (venv pip itself upgraded 25.2 → 26.3 to clear installer-only
  advisories).
- ✅ `npm audit --omit=dev` (2026-11-15): **0 vulnerabilities** in production
  dependencies (test-results/npm-audit.json).
- ⚠️ Accepted dev-only risk: `npm audit` (incl. dev) reports 8 moderate
  advisories, all `minimatch` DoS via the typescript-eslint / eslint-config-next
  lint toolchain. No runtime exposure; the only npm-suggested fix is a breaking
  downgrade (eslint-config-next 15.5.29), so it is deferred until upstream
  ships a non-breaking fix. Re-check on dependency upgrades.
- ✅ Dependency audits wired into CI (backend `pip-audit`, frontend
  `npm audit --omit=dev` — both fail the pipeline on findings).

## Data protection
- ✅ Password hashes and refresh tokens stored hashed only.
- ✅ Structured logs never record bodies, tokens, cookies or keys.
- ✅ Backups contain user data — encrypt/access-control/rotate (BACKUP_RECOVERY.md).

## Launch blockers (user-gated)
- ⚠️ Real LLM key, real email provider, real payment activation, public
  release — all require explicit approval (LAUNCH_CHECKLIST.md).
