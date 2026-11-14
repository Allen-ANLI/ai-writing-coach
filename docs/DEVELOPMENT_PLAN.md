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
| System Design V1.1 | **Done** — user supplied `docs/AI_Writing_Coach_System_Design_V1.1.md` 2026-11-14; committed in `7baeb36` |
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

**Status:** IMPLEMENTED 2026-11-14, verified, **included in baseline commit 7e4aa60**.
No backend or database changes in this slice.

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

## 3c. Stage 2 — Slice 2A: Essay Management

**Status:** IMPLEMENTED 2026-11-14, re-verified 2026-11-15 (pytest 94 passed, ruff/tsc/
ESLint/build clean, Playwright 18 passed), **committed as `7baeb36`** on `main`
(checkpoint commit under Master Development Directive V2.0 autonomous authority).

Phase 0 (stable baseline):

- Contract fix (user-approved): `POST /auth/register` now documents
  `409 RESOURCE_ALREADY_EXISTS` (ErrorResponse schema). Full OpenAPI 3.1 validation:
  0 errors; no unrelated API changes; permanent regression test added.
- `.gitignore` audited; `git check-ignore` confirms .env, node_modules, .venv,
  .tools, .next, test-results, caches, egg-info all excluded.
- Baseline commit `7e4aa60` `feat: complete infrastructure and authentication`
  (111 files: Stage 1 + Slice 1 backend auth + Slice 1.5 frontend auth). No temp
  files or local test data included.

Phase 1 scope delivered:

- Migration `0003_essay_tables`: `essays`, `essay_working_documents`,
  `essay_versions` (ERD V1.2 §6.1–6.4). Composite FKs enforce same-essay version
  pointers and parent chains; UNIQUE(essay_id, version_no) and UNIQUE(essay_id, id);
  ERD indexes. No `current_version_id`. `question_id` FK deferred until
  ielts_questions exists (later slice); UUID format validated now.
- 5 endpoints: POST/GET list/GET/PATCH/DELETE `/essays[/{id}]`, all authenticated,
  user-scoped, foreign/deleted resources → 404, soft delete via deleted_at.
- Atomic creation: essay + empty working document (revision 1, sha256 content hash)
  + immutable original snapshot (version_no 1) in one transaction; rollback test
  proves all-or-nothing.
- Cursor pagination: opaque base64 (created_at, id) seek, limit 1–100 default 20.
- PATCH accepts title only (extra fields rejected); Idempotency-Key accepted per
  contract, dedup storage reserved for a later slice.
- Frontend: protected `/dashboard` (list/create/rename/delete-with-confirmation,
  loading/empty/error states) and `/essays/[id]` detail (Suspense-wrapped dynamic
  param for Next 16 prerendering); TanStack Query mutations with invalidation.
- Tests: backend **94 passed** (16 new essay integration tests on real PostgreSQL:
  atomicity, rollback, pagination, isolation, soft delete, invalid question id,
  same-essay constraint, snapshot immutability); frontend E2E **18/18 passed**
  (7 new essay scenarios incl. loading state, delete confirmation, detail nav).
  ruff / tsc / ESLint / production build all pass.
- Decisions flagged for approval: provisional essays.status CHECK
  ('active','archived') — ERD does not enumerate values; essay list/detail response
  shapes (contract leaves them open) follow API Spec §2 envelope + ERD fields.

## 3d. Stage 2 — Slice 2B: Working Document, snapshots, versions, restore

**Status:** IMPLEMENTED 2026-11-15 under Directive V2.0, verified: backend **144 passed**
(50 new tests), ruff check/format clean. Migration `0004` applied to dev + test DBs.

Scope delivered:

- `GET/PUT /essays/{id}/working-document`: optimistic concurrency on `base_revision`
  (409 `WORKING_DOCUMENT_CONFLICT`, no partial write), server-side TipTap JSON →
  plain text + word count derivation (client values validated when supplied),
  revision increment, NO snapshot on autosave, essay.updated_at bump.
- `POST /essays/{id}/snapshots`: exact-current-revision requirement (409
  `DOCUMENT_VERSION_CONFLICT`), version_no sequence, parent chain, optional label;
  `original`/`ai_rewrite` types rejected here (created only by essay creation /
  rewrite acceptance). Idempotency-Key dedup implemented (see below).
- `GET /essays/{id}/versions` (cursor pagination) and `GET .../versions/{version_id}`.
- `POST /essays/{id}/restore`: atomic copy into Working Document + revision increment
  + `restore` Edit Event (from/to revisions, before/after text); source snapshot
  immutable; 409 on revision conflict.
- Migration 0004: `essay_edit_events` (ERD §6.5, composite same-essay FKs; issue/
  suggestion FKs deferred to Grammar slice), `essay_versions.label` (R3),
  `idempotency_keys` (R10).
- `app/core/idempotency.py`: per-user Idempotency-Key store; replay on same
  key+payload, 422 on key reuse with different payload, 429 for in-flight repeats,
  60s stale-placeholder reclamation. Applied to snapshots; reused by later slices.
- Defects found and fixed by the new tests: (1) stale identity-map attributes under
  SELECT FOR UPDATE after the joined essay load — fixed with `populate_existing`
  (same trap the auth module documents); (2) psycopg reports rowcount -1 for
  INSERT ON CONFLICT DO NOTHING — conflict detection switched to RETURNING.
- Contract operations now 21/87; permanent no-out-of-contract-routes test added.
- ERD updated to V1.2.1 increments (label, status enums, idempotency table, edit
  events); traceability matrix updated.

Out of scope (next slices): TipTap editor frontend (2C), writing sessions (2D),
issue archiving into snapshots (arrives with writing_issues in Slice 3).

## 3e. Stage 2 — Slice 2C: TipTap writing editor

**Status:** IMPLEMENTED 2026-11-15 under Directive V2.0, verified: Playwright
**25 passed** (7 new editor tests), Vitest **12 passed**, tsc/ESLint/build clean.

Scope delivered:

- `/essays/[id]` is now the writing editor (confirmed inline-first layout: wide
  center canvas, collapsible left outline expanded by default, no right panel;
  narrow screens get an outline overlay). Existing essay E2E contracts preserved.
- TipTap StarterKit: paragraphs/headings/bold/italic/lists/quote, undo/redo.
- Autosave: 1.5s debounce, optimistic concurrency, save-status bar, Ctrl/Cmd+S,
  beforeunload guard, IME-composition-safe (no saves mid-composition).
- Conflict recovery: 409 keeps local edits, pauses saving, offers Copy my text /
  Load latest version; never silently overwrites.
- Version history dialog: list, read-only view, checkpoint creation (label +
  Idempotency-Key), confirmed restore (atomic server-side; editor refreshed).
- `lib/text-positions.ts`: unicode_codepoint ↔ UTF-16 ↔ ProseMirror mapping
  (AGENTS invariant) + `lib/document-text.ts` word-count rule mirroring the
  server; 12 Vitest unit tests incl. emoji/CJK round-trips.
- OpenAPI type generation (R11 resolved): `npm run generate:api` resolves YAML
  anchors and emits `src/types/generated.ts` (15 schemas); api.ts re-exports.
- Dependencies: @tiptap/react, @tiptap/starter-kit, @tiptap/pm; dev: vitest, yaml,
  @types/node ^22 (matches the portable Node 22 runtime; vitest 5 peer requires it).
- Defects found and fixed by tests: toolbar commands were no-ops on a fresh
  unfocused editor (selection at doc level) — ensureFocus places caret inside the
  document; descendants() callback pruning broke position mapping; the longer
  E2E suite exhausted production register rate limits — relaxed ONLY in the
  isolated E2E backend env.
- `awc-screenshots.mjs` review utility recreated (referenced by the user but absent
  from the repository); captures landing/login/register/profile/dashboard/editor/
  history against the dev stack into gitignored test-results/screenshots.

Out of scope (next slices): writing sessions + modes (2D), grammar feedback (3).

## 3a. Autonomous execution under Master Development Directive V2.0 (2026-11-15)

The user's Directive V2.0 grants full autonomous engineering authority to complete the
entire product (all PRD features, AI, monetization infrastructure, production readiness)
without per-slice approval gates. Human approval is required only for: new material
external costs, purchasing/activating paid services, irreversible destructive data
operations, material legal/privacy risks, and public deployment/release. No partial,
alpha, beta or early-access launch is permitted; internal builds and testing are.

Engineering obligations per slice: tests with the implementation, narrowest relevant
suite + lint/type checks run and reported honestly, contract/docs kept in sync
(`TRACEABILITY_MATRIX.md` updated), small imperative commits on `main`, never
force-push/reset, applied migrations never edited in place.

Dependency-aware slice roadmap (internal execution decision, not an approval gate):

| Slice | Scope | Depends on |
|---|---|---|
| 2B | Working Document GET/PUT (autosave, optimistic concurrency), snapshots, versions list/detail, restore; migration 0004 (writing_sessions, essay_edit_events, essay_versions.label) | 2A |
| 2C | TipTap editor on /essays/[id]: autosave UI, save status, conflict handling, word count, undo/redo, left outline, version history + restore UI; unicode_codepoint↔ProseMirror mapping; OpenAPI type generation pipeline | 2B |
| 2D | Writing sessions (assisted/independent), backend-enforced mode feature flags, submit → Final Snapshot; exam config; frontend mode controller | 2B |
| 3 | Grammar core: LanguageTool service + custom rules, issue lifecycle, validate/reveal/ignore; LLM provider abstraction + prompt versioning + ai_usage_logs; contextual teaching | 2D |
| 4 | Expression polish, Chinese→English, suggestion accept; knowledge base CRUD + archive | 3 |
| 5 | Embeddings + pgvector RAG, search, previously-learned recommendations, extraction workflow; reviews (SM-2), progress, weakness profile + trends, learning summary | 4 |
| 6 | IELTS question bank (original licensed-safe seed), tags, favorites, random | 2D |
| 7 | Evaluations (IELTS 4-criteria estimates, queued), rewrites level 1–4, atomic accept | 3, 6 |
| 8 | Outlines CRUD + confirm; Writing Planner / Learning Extractor / Study Planner LangGraph workflows (checkpointed, human confirmation) | 5, 7 |
| 9 | Learning plans/tasks, personalized recommendations, analytics AI usage endpoints, dashboard analytics | 5 |
| 10 | Commercialization: plans/entitlements/quotas/metering, subscription lifecycle, payment sandbox integration, billing history (activation gated on user approval) | 9 |
| 11 | Production readiness: deployment config, backup/recovery, structured logging/monitoring, rate limiting hardening, CI/CD, security review, privacy (account deletion/export), performance + AI quality evaluation reports | all |

## 3b-history. Earlier "TBC" note (superseded)

`API_SPECIFICATION.md` section 21 lists MVP feature phases (Phase 1 Auth/Essay/Grammar,
Phase 2 Expression/Evaluation, Phase 3 Knowledge Base/Review, Phase 4 IELTS/Outline/
LangGraph/Analytics). Those are **product feature priorities**. The engineering slice
roadmap above (Directive V2.0) supersedes the earlier "no approved stage plan" note.

## 4. Tracked issues awaiting decision

| # | Issue | Detail | Blocking |
|---|---|---|---|
| 1 | ~~4 pre-existing OpenAPI validation errors~~ **RESOLVED (2026-11-14)** | User approved adding the missing path parameter declarations (additive only). Fixed on `PATCH /writing-sessions/{session_id}` (`session_id`), `PATCH /essays/{essay_id}/issues/{issue_id}` (`essay_id`, `issue_id`), `PATCH /outlines/{outline_id}` (`outline_id`). Full OpenAPI 3.1 validation now reports **0 errors**; structural diff vs the pre-Health baseline confirms only the approved Stage 0 additions plus these 4 declarations changed. `info.version` stays 1.1.1 (omission fix, no semantic change). | No longer blocking |
| 2 | ~~System Design V1.1 missing~~ **RESOLVED (2026-11-14)** | User supplied `docs/AI_Writing_Coach_System_Design_V1.1.md`; committed in `7baeb36` | No longer blocking |
| 3 | **OpenAPI uses YAML anchors/aliases** | e.g. `WorkingDocumentUpdate: *id002`. Validation handles them; type generation must resolve aliases first | Future type generation |
| 4 | ~~Docker daemon not running~~ **RESOLVED (2026-11-14)** | User started Docker Desktop manually (decision E). `awc-db` (pgvector/pgvector:pg17) is up and healthy; real integration tests executed and passed. No Docker/WSL/system config changes made | No longer blocking |
| 5 | ~~Git not initialized~~ **RESOLVED** | Repository on `main`: baseline `7e4aa60` (infra + auth), checkpoint `7baeb36` (Slice 2A essay management + System Design V1.1 + handoff). Directive V2.0 authorizes ordinary commits; force-push/reset remain forbidden | No longer blocking |
| 6 | **pip global index unreachable** | Global config points at a Tsinghua mirror that returned no distributions. Official PyPI used per-command via `--index-url`; global config left untouched | Dependency installs need explicit `--index-url` |
| 7 | **Port 3000 excluded by Windows** | Hyper-V/WinNAT reserved range 2955–3054 blocks binding 3000 (EACCES). Frontend adapted to port **3500**; CORS default origin updated. System port exclusions were NOT modified. Ranges can shift across reboots; if 3500 is ever reserved, pick another free port and update `CORS_ORIGINS` + scripts | None (worked around in app config) |
| 8 | **Starlette TestClient deprecation warning** | starlette 1.10 warns that httpx-based TestClient is deprecated in favor of httpx2. Tests pass; warning only. Revisit when upgrading test tooling | None |

## 5. Change log

| Version | Change |
|---|---|
| Plan 2026-11-15 | Directive V2.0 autonomous execution adopted; slice roadmap 2B→11 added; System Design V1.1 present; Slice 2A re-verified and committed (`7baeb36`); `TRACEABILITY_MATRIX.md` created with reconciliation record R1–R12 |
| Contract 1.1.1 | Additive `GET /health` endpoint, `HealthResponse` schema, `Health` tag; API Spec revision V1.1.1 adds section 23 and error code `DATABASE_UNAVAILABLE`. No approved business semantics changed |
| Contract 1.1.1 (omission fix, 2026-11-14) | User-approved: declared the 4 previously omitted path parameters on three `PATCH` operations. Additive declarations only; no business semantics changed, version unchanged. Full OpenAPI 3.1 validation: 0 errors |