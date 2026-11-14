# Development Plan

**Scope of this file:** records only what is explicitly agreed in `AGENTS.md` and
`MONOREPO_INITIALIZATION_TASKS.md` V1.0. Later stages are marked **TBC** and are not
invented here.

## 1. Stage 0 — Contract and document setup

**Status:** preparation complete (pending human confirmation).

| Item | State |
|---|---|
| Repository root `ai-writing-coach/` created | Done |
| `AGENTS.md` at repository root | Done (moved, hash-verified) |
| `docs/DATABASE_ERD.md` (ERD V1.2) | Done (moved, hash-verified) |
| `docs/API_SPECIFICATION.md` (API Spec V1.1) | Done (moved, hash-verified) |
| `contracts/openapi.yaml` (OpenAPI 3.1) | Done (moved, hash-verified) |
| PRD V1.1 preserved as `docs/PRD_V1.1.docx` | Done (moved, hash-verified) |
| System Design V1.1 | **MISSING** — recorded, not fabricated |
| `docs/README.md` authority index | Done |
| `docs/DEVELOPMENT_PLAN.md` | Done |
| Exactly one OpenAPI file | Verified |
| Health API added to contract + spec | Done, additive, consistency-verified |

## 2. Stage 1 — Repository bootstrap

**Status:** IMPLEMENTED 2026-11-14, verified locally, **awaiting human review**
(no Git init/commit per instruction).

Agreed scope (from `AGENTS.md` section 10 and the task list):

- Next.js App Router frontend, TypeScript strict mode, Tailwind CSS, ESLint.
- FastAPI backend with a database-aware `GET /api/v1/health`.
- PostgreSQL + pgvector via Docker Compose, persistent volume, `pg_isready` healthcheck.
- Environment examples, local-only CORS, README instructions.
- Minimal backend smoke test and frontend health check.

Implementation and verification record (2026-11-14):

- Frontend: Next.js **16.4.6** (App Router, Turbopack), React 19.3, TypeScript strict,
  Tailwind CSS 4.3, ESLint 9. Landing page with a typed client-side health check.
  `npm run lint`, `npx tsc --noEmit`, `npm run build` all pass.
- Backend: FastAPI 0.162.7, SQLAlchemy 2.1.8, Alembic 1.20.1, psycopg 3.3.9,
  pydantic-settings. Migration `0001_enable_pgvector` applied (`alembic current` = 0001 head).
  No business entities. `pytest`: **22 passed** (3 health smoke, 4 contract, 10 CORS,
  1 compose, 1 alembic URL, 3 real-DB integration). `ruff check` / `ruff format --check` pass.
- Database: `pgvector/pgvector:pg17`, container `awc-db` healthy (`pg_isready`),
  vector **0.8.7** enabled, named volume `pgdata` persists across stop/start.
- End-to-end: real HTTP 200 → stopped DB → real 503 `DATABASE_UNAVAILABLE` envelope →
  restarted DB → 200. CORS allows only the local frontend origin; foreign origin rejected.
- **Local frontend port is 3500, not 3000**: port 3000 lies inside a Windows
  Hyper-V/WinNAT excluded port range (2955–3054) on this machine; binding fails with
  EACCES. No system configuration was changed (decision E); the app port and CORS
  default were adapted instead. See root README.

Review hardening pass (2026-11-14, user-approved limited changes; no business or
contract changes, no dependency upgrades):

- CORS `allow_methods`/`allow_headers` are explicit whitelists
  (GET/POST/PUT/PATCH/DELETE; Content-Type/Authorization/Idempotency-Key);
  origins remain local-only (`http://localhost:3500`).
- Compose binds PostgreSQL to `127.0.0.1` only. Consequence found and fixed:
  `localhost` resolves to `::1` first, which Docker's IPv6 relay blackholes after
  the IPv4-only rebind; local default `DATABASE_URL` now uses `127.0.0.1`, and the
  Alembic engine gained the same `connect_timeout` as the app engine.
- Alembic URL no longer passes through ConfigParser interpolation: percent-encoded
  credentials (e.g. `p%40ss`) work; covered by an offline-SQL subprocess test.
- Migration 0001 `downgrade` is an intentional no-op: rollback never drops the
  vector extension (future dependent objects stay safe); removal is manual only.

Environment preparation completed in advance:

- Portable Node.js **v22.23.5** (npm 10.9.9) in `.tools/`, no machine-level install.
- Python **3.13.9** virtual environment at `backend/.venv`, isolated from Anaconda base.

Explicitly out of scope for Stage 1: authentication, all 29 ERD models, full domain
migrations, TipTap, Essay CRUD and autosave, LanguageTool, grammar issue lifecycle, LLM
providers and prompts, evaluation and rewrite, embeddings/RAG, LangGraph, Redis, Celery,
Kubernetes, billing, production deployment.

## 3. Stage 2 — Slice 1: Backend Authentication

**Status:** IMPLEMENTED 2026-11-14 (explicit user approval), verified, awaiting review.
No Git commits.

Scope delivered (user-approved slice definition):

- ERD V1.2 §5 entities only: `users`, `user_profiles`, `auth_sessions`,
  `auth_refresh_tokens` (SQLAlchemy 2.x typed models; migration `0002`, 0001 untouched).
- 9 endpoints: register / login / refresh / logout / logout-all / sessions list /
  session revoke / users.me GET / users.me PATCH.
- Argon2id passwords; HS256 JWT (signature/exp/iss/aud, fixed algorithm); opaque
  high-entropy refresh tokens stored as SHA-256 hashes; HttpOnly+Secure+SameSite=Strict
  cookie scoped to /api/v1/auth; rotation in one transaction without new sessions;
  consumed-token reuse revokes family + session; session-first row locking with
  populate_existing re-reads; CSRF via SameSite + Origin check; in-process rate-limit
  reservation for register/login; identity always from verified auth context.
- Tests: 55 new auth integration tests on a dedicated real PostgreSQL test database
  (`ai_writing_coach_test`), plus all Stage 1 tests. Total **77 passed**; ruff clean.
  A live end-to-end smoke (register → me → patch → refresh → sessions → reuse
  detection → re-login → logout → revoked refresh) also passed against the dev server.
- New dependencies: argon2-cffi, PyJWT, email-validator (no major upgrades).
- OpenAPI contract: **unchanged**. Known gaps reported, not edited: register 409
  (RESOURCE_ALREADY_EXISTS) is not in the contract's register response list; auth
  response bodies follow API Spec §3.2 examples (contract leaves them open);
  PATCH /users/me validates an explicit field set within the contract's open object.

Out of scope for this slice (unchanged): frontend auth pages, Essay CRUD, Working
Document, TipTap, LanguageTool, LLM, RAG, LangGraph, Redis, Celery, Kubernetes.

## 3b. Stage 2 — Slice 1.5: Frontend Authentication

**Status:** IMPLEMENTED 2026-11-14 (explicit user approval), verified, awaiting review.
No Git commits. No backend or database changes in this slice.

Scope delivered:

- Pages: `/login`, `/register`, `/profile` (protected; current user profile + device
  sessions), auth-aware landing navigation.
- `lib/api-client.ts`: in-memory access token only; `credentials: "include"` on every
  request; single-flight refresh shared by concurrent 401s; original request retried
  exactly once and only on 401 (rejected before business logic, so non-idempotent
  requests cannot double-execute); refresh failure clears token + query cache and
  drops the auth state; no token/cookie logging.
- `features/auth/`: AuthProvider (React Context) with silent-refresh session restore
  on mount (page-reload recovery), login/register/logout; RequireAuth route guard;
  TanStack Query for server state (profile, sessions) per AGENTS.md.
- Refresh token stays exclusively in the HttpOnly+Secure+SameSite=Strict cookie
  (Path=/api/v1/auth); never read or stored by JavaScript; backend CSRF Origin check
  respected (browser sends Origin automatically).
- New dependencies: @tanstack/react-query (AGENTS stack), @playwright/test (dev).
- Tests: Playwright E2E **11/11 passed** on an isolated stack (backend :8001 against
  ai_writing_coach_test with 2s access TTL, frontend :3600; auto-created/migrated by
  globalSetup via scripts/prepare_e2e_db.py). Covers register, login success/failure,
  reload restore, expiry auto-refresh, concurrent-401 single refresh (count === 1),
  failed-refresh sign-out, logout irrecoverability, protected-route redirect,
  authenticated access, cookie invisibility + attributes. `tsc --noEmit`, ESLint,
  production build all pass.
- Browser channel: Playwright CDN download stalls on this machine; tests run on the
  installed Chromium-based Edge via `channel: "msedge"` (config documents how to
  switch to the bundled Chromium).

## 3a. Later stages — TBC

`API_SPECIFICATION.md` section 21 lists MVP feature phases (Phase 1 Auth/Essay/Grammar,
Phase 2 Expression/Evaluation, Phase 3 Knowledge Base/Review, Phase 4 IELTS/Outline/
LangGraph/Analytics). Those are **product feature priorities**, not an approved
engineering stage plan.

Beyond the approved Stage 2 Slice 1 above, no further engineering stage plan has been
approved. It is **TBC** and will not be invented here. System Design V1.1 is a
prerequisite for architectural decisions in those stages.

## 4. Tracked issues awaiting decision

| # | Issue | Detail | Blocking |
|---|---|---|---|
| 1 | ~~4 pre-existing OpenAPI validation errors~~ **RESOLVED (2026-11-14)** | User approved adding the missing path parameter declarations (additive only). Fixed on `PATCH /writing-sessions/{session_id}` (`session_id`), `PATCH /essays/{essay_id}/issues/{issue_id}` (`essay_id`, `issue_id`), `PATCH /outlines/{outline_id}` (`outline_id`). Full OpenAPI 3.1 validation now reports **0 errors**; structural diff vs the pre-Health baseline confirms only the approved Stage 0 additions plus these 4 declarations changed. `info.version` stays 1.1.1 (omission fix, no semantic change). | No longer blocking |
| 2 | **System Design V1.1 missing** | No approved architecture document in workspace | Architectural decisions beyond bootstrap |
| 3 | **OpenAPI uses YAML anchors/aliases** | e.g. `WorkingDocumentUpdate: *id002`. Validation handles them; type generation must resolve aliases first | Future type generation |
| 4 | ~~Docker daemon not running~~ **RESOLVED (2026-11-14)** | User started Docker Desktop manually (decision E). `awc-db` (pgvector/pgvector:pg17) is up and healthy; real integration tests executed and passed. No Docker/WSL/system config changes made | No longer blocking |
| 5 | **Git not initialized** | Deliberately left uninitialized during Stage 1 per user instruction "不提交 Git，等待我审查". `git init` + branch `feature/bootstrap-monorepo` + first commit await explicit user approval | Git-based checks (`git diff --check` etc.) deferred |
| 6 | **pip global index unreachable** | Global config points at a Tsinghua mirror that returned no distributions. Official PyPI used per-command via `--index-url`; global config left untouched | Dependency installs need explicit `--index-url` |
| 7 | **Port 3000 excluded by Windows** | Hyper-V/WinNAT reserved range 2955–3054 blocks binding 3000 (EACCES). Frontend adapted to port **3500**; CORS default origin updated. System port exclusions were NOT modified. Ranges can shift across reboots; if 3500 is ever reserved, pick another free port and update `CORS_ORIGINS` + scripts | None (worked around in app config) |
| 8 | **Starlette TestClient deprecation warning** | starlette 1.10 warns that httpx-based TestClient is deprecated in favor of httpx2. Tests pass; warning only. Revisit when upgrading test tooling | None |

## 5. Change log

| Version | Change |
|---|---|
| Contract 1.1.1 | Additive `GET /health` endpoint, `HealthResponse` schema, `Health` tag; API Spec revision V1.1.1 adds section 23 and error code `DATABASE_UNAVAILABLE`. No approved business semantics changed |
| Contract 1.1.1 (omission fix, 2026-11-14) | User-approved: declared the 4 previously omitted path parameters on three `PATCH` operations. Additive declarations only; no business semantics changed, version unchanged. Full OpenAPI 3.1 validation: 0 errors |