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

## 3f. Stage 2 — Slice 2D: Writing sessions and modes

**Status:** IMPLEMENTED 2026-11-15 under Directive V2.0, verified: backend
**158 passed** (14 new session tests), Playwright **30 passed** (5 new), vitest 12,
tsc/ESLint/build clean, ruff clean. Migration `0005` applied to dev + test DBs.

Scope delivered:

- Migration 0005: `writing_sessions` (ERD §6.3) + `essays UNIQUE(id, user_id)` +
  composite FK `(essay_id, user_id) → essays(id, user_id)` enforcing same-owner
  at the database level (ERD §15.1). Session status enumeration adopted:
  active / submitted / cancelled (recorded in ERD).
- 5 endpoints: POST/GET `/essays/{id}/sessions`, GET/PATCH `/writing-sessions/{id}`,
  POST `/writing-sessions/{id}/submit` (Idempotency-Key dedup).
- Exactly two modes; `enabled_features` always server-derived (SD §10): independent
  disables realtime grammar/LLM/Chinese→English/expression recommendations/Ghost
  Text/paragraph analysis; autosave + post-submission evaluation stay on. Grammar
  and AI slices must check these flags backend-side.
- exam_config validated (mock_exam only): exam_type, task_type, duration_minutes
  (1–180), optional word_limit; deadline_at derived; submit after deadline → 400.
- One active session per essay (409 RESOURCE_ALREADY_EXISTS); cancel frees it.
- Atomic submit: revision check (409 WORKING_DOCUMENT_CONFLICT, no partial write),
  Final Snapshot — shared with Original when content hashes match (API Spec §5),
  essay.final_version_id pointer, session state, submit Edit Event.
- Frontend: session controls bar in the editor — start dialog (mode/activity/exam
  config), mode chip, independent-mode notice, live exam countdown, submit with
  confirmation (requires clean save state), cancel, submitted state.
- Defect fixed during implementation: composite FK remote columns must be fully
  qualified (`essays.user_id`) in both migration and model.

Out of scope (next slices): grammar checking + issue lifecycle (3), LLM teaching (3).

## 3g. Stage 2 — Slice 3: Grammar core + LLM abstraction + inline feedback

**Status:** IMPLEMENTED 2026-11-15 under Directive V2.0, verified: backend
**204 passed** (46 new), Playwright **37 passed** (7 new), vitest 12,
tsc/ESLint/build/ruff clean. Migration `0006` applied.

Scope delivered:

- Infrastructure: LanguageTool self-hosted via Docker Compose (meyay/languagetool
  image, host port 8010, loopback-only). The erikvl87 :latest build ships 0-byte
  jars and :6.6 ships Java 11 for Java-17 classes — both rejected. Docker data
  moved C:→D: with user authorization (C: was full; junctions keep paths stable).
- Migration 0006: writing_issues, issue_suggestions, issue_teachings,
  ai_usage_logs (ERD §7, §14); deferred edit-event issue/suggestion FKs attached.
- Rule-first pipeline (SD §5): LanguageTool + custom deterministic rules
  (Chinese punctuation, missing space after punctuation), category mapping per
  PRD FR-02.3, Chinese short-explanation templates, reliability classification;
  LLM deep check ONLY for uncertain fragments (max 3/check); deterministic hits
  never call an LLM (asserted by tests). Graceful degradation to custom rules
  with check_status=partial when LanguageTool is down.
- Issue lifecycle: grammar-check (mode + revision + text_range validation),
  list/detail (masked suggestions), validate (atomic: rule re-check accepts any
  valid alternative, re-anchors incorrect issues, stale-marks siblings, Edit
  Event, second revision check), reveal (explicit only), ignore, teaching
  (context-hash cache, personalized_note forced null without verified history).
- LLM abstraction (SD §7): provider protocol, deterministic mock (dev/test,
  zero cost, labeled), OpenAI-compatible adapter (config-driven, retries,
  timeout mapping), Pydantic-validated structured outputs, versioned prompt
  registry, ai_usage_logs for every call (provider/model/prompt/tokens/latency/
  cost/status). **No provider keys configured — real-provider activation and
  AI linguistic-quality evaluation await user keys (reported decision).**
- Frontend: grammar TipTap extension (category-colored wavy underlines, hint
  widgets with blurred •••• answers, transaction-mapped ranges dropped when
  unreliable), use-grammar orchestration (checks after saves, stale discard,
  auto-validation of edited issues, reveal/ignore/teach, Alt+R/T/I shortcuts),
  floating teaching card, Check now + issue count controls, independent-mode
  enforcement (no controls, backend 403).
- Offsets: unicode_codepoint end-to-end; LT UTF-16 converted at the adapter
  boundary; emoji/CJK round-trip tests on both sides.

Out of scope (next slices): expression polish/translation (4), knowledge base (5).

## 3h. DeepSeek integration + finalized editor UX (user update 2026-11-15)

**Status:** IMPLEMENTED 2026-11-15, verified: backend 215+ passed, Playwright
**38 passed**, vitest 21, tsc/ESLint/build/ruff clean. Contract 1.2.0 (34/87).
ADRs: ADR-016 (finalized editor UX), ADR-017 (DeepSeek provider).

Scope delivered:

- DeepSeek provider (`LLM_PROVIDER=deepseek`): OpenAI-compatible chat
  completions + Anthropic-compatible messages when base URL ends /anthropic;
  env-only credentials; defensive usage parsing; honest 4xx surfacing (no
  silent model fallback); timeout/retry mapping. Mock strictly separated:
  pytest + E2E force mock. `scripts/verify_llm.py` (connectivity/model/usage)
  and `scripts/eval_ai.py` (grammar deep-check + teaching datasets, metrics,
  per-call usage/cost, JSON reports) ready; harness validated with mock.
- Finalized UX (ADR-016): separate non-editable question section
  (essays.question_prompt, migration 0007, create-dialog field); hierarchical
  collapsible text outline (sections→paragraphs→sentence ideas); automatic
  sentence-completion checking with robust boundaries (abbreviations,
  decimals, initials, quotes, paragraph breaks, IME, paste) + debounce +
  AbortController cancellation + stale-revision discard; hover floating
  feedback card (translucent, non-obstructing); click-blurred-to-reveal (no
  reveal button); Tab-to-accept only while pinned (normal Tab otherwise);
  teaching icon → contextual card; no manual check button; no Submit button
  during writing (post-writing evaluation actions arrive in Slice 7).
- New atomic acceptance: POST /essays/{id}/issues/{id}/accept applies the
  server-stored suggestion (never client text) with revision check, issue
  resolution, suggestion state, Edit Event; server-side TipTap range
  replacement utility (codepoint-exact, marks preserved, cross-paragraph
  ranges rejected).
- Tests: 6 acceptance integration tests, 7 range-replacement unit tests,
  9 sentence-splitter unit tests; grammar/sessions E2E rewritten to the
  finalized interactions (38 total passing).

**Open item (user action):** place the newly rotated DeepSeek API key in
`.env` (`LLM_API_KEY=`). The credential exposed in the chat attachment was
NOT used. Real AI quality evaluation runs once the key is present.

## 3i. Stage 2 — Slice 4: Expression assistance + knowledge base

**Status:** IMPLEMENTED 2026-11-15, verified: backend **230 passed** (15 new),
Playwright **42 passed** (4 new), vitest 21, tsc/ESLint/build/ruff clean.
Migrations 0008/0009 applied. Contract operations 44/87.

Scope delivered:

- Migrations 0008/0009: user_expressions, expression_sources (ERD §9.1–9.2),
  expression_suggestions + items (ERD §9.6 extension — the contract's accept
  endpoint needs persisted candidates), essay_edit_events.expression_suggestion_id
  (separate from grammar suggestion_id; FK integrity preserved for both).
- Knowledge base: owner-scoped CRUD, case-insensitive dedup on create, soft
  delete, archive, keyword search (English/Chinese), status/topic filters,
  cursor pagination, typed sources with essay-ownership validation.
- Polish + Chinese→English: backend mode enforcement (403 in independent),
  revision guards, LLM outside transactions, persisted candidates, usage
  logging; previously-learned candidates recalled from the user's OWN knowledge
  base (keyword now; pgvector semantic in Slice 5) and labeled only when the
  LLM output matches a stored expression.
- Atomic acceptance: client submits the replacement document; server validates
  ownership/revision/range and that the chosen expression is present, then
  updates document + suggestion state + Edit Event in one transaction.
- Frontend: selection-driven floating assistance (Improve expression /
  Translate to English), candidate cards with previously-learned badges,
  server-authoritative apply (no autosave race), save-to-knowledge-base action,
  /knowledge page (add/search/filter/archive/delete), nav link.
- Defect fixed during implementation: expression acceptance initially reused
  essay_edit_events.suggestion_id (FK to grammar issue_suggestions) → FK
  violation; added the dedicated expression_suggestion_id column.
- Tests: 6 CRUD + 9 assistance integration tests; 4 E2E (KB CRUD, polish
  accept + save-to-KB, translation apply, independent-mode enforcement).

Out of scope (next slices): semantic RAG + extraction + learning (5), IELTS (6),
evaluations/rewrites as post-writing actions (7), outlines/LangGraph (8).

## 3j. Stage 2 — Slice 5A: Semantic RAG + expression extraction

**Status:** IMPLEMENTED 2026-11-15, verified: backend **245 passed** (15 new),
Playwright **44 passed** (2 new), vitest 21, tsc/ESLint/build/ruff clean.
Migration 0010 applied. Contract operations 45/87.

Scope delivered:

- Embedding provider abstraction (`app/ai/embeddings.py`): deterministic mock
  (tests only, NOT semantic) + OpenAI-compatible endpoint adapter with
  dimension validation. Config: EMBEDDING_PROVIDER/BASE_URL/API_KEY/MODEL/
  DIMENSIONS (1536 must match the vector column).
- Migration 0010: expression_embeddings VECTOR(1536), HNSW cosine index,
  UNIQUE(expression_id, embedding_model, content_hash) — rebuildable vectors.
- Embeddings written on expression create/update (best-effort: provider
  failure never blocks knowledge-base writes).
- Semantic retrieval ALWAYS user-scoped at query time (join + WHERE user_id),
  never a post-filter; archived/deleted excluded. Keyword/semantic/hybrid
  search modes; previously-learned recall upgraded to semantic-first with
  keyword fallback (suitability still judged by the LLM).
- Extraction (POST /essays/{id}/expressions/extract, 202): from an IMMUTABLE
  version, LLM candidates returned for confirmation; nothing persisted until
  the user saves via POST /expressions (source_type=essay).
- Frontend: /knowledge search-mode selector; History → Extract per version →
  confirmation dialog with per-candidate selection.
- Tests: 3 embedding unit + 8 RAG/extraction integration + 2 E2E (semantic
  modes, extraction confirmation flow).
- Dependency added: pgvector>=0.3 (Python client for the vector column).

**Quality caveat:** mock embeddings verify the pipeline only; real semantic
quality requires a configured embedding endpoint (reported with the LLM key
open item).

Out of scope (next): Slice 5B reviews/SM-2/progress/weaknesses/summary, then
IELTS (6), evaluations/rewrites (7), outlines/LangGraph (8), analytics (9),
billing (10), production readiness (11).

## 3k. Stage 2 — Slice 5B: Learning (reviews, SM-2, weaknesses)

**Status:** IMPLEMENTED 2026-11-15, verified: backend **262 passed** (17 new),
Playwright **47 passed** (3 new), vitest 21, tsc/ESLint/build/ruff clean.
Migration 0011 applied. Contract operations 53/87.

Scope delivered:

- Deterministic SM-2 spaced repetition (`learning/sm2.py`, unit-tested):
  1d/6d/ease-multiplied intervals, ease floor 1.3, failure reset, mastery rule
  (streak ≥ 5 and interval ≥ 21d). Scheduling/mastery NEVER LLM-decided.
- Migration 0011: expression_progress (UNIQUE(user, expression), same-owner
  composite FK via user_expressions UNIQUE(id, user_id), non-negative counts),
  expression_reviews (reference snapshot, score, feedback), user_weaknesses
  (UNIQUE(user, category, sub_category), sub_category NOT NULL DEFAULT '').
- Reviews: due prompts show Chinese only (no answer leakage); rule-first
  normalized exact match passes without LLM; otherwise LLM semantic judging
  accepts any natural correct translation (ReviewJudgement schema); review
  records + progress counters + next_review_at; usage logged.
- Progress + learning summary endpoints (counts by status, due now, reviewed
  today, mastered, total reviews).
- Weaknesses: aggregated on issue detection (record_weakness_occurrence hook
  in grammar check), category detail with recent examples, volume-adjusted
  weekly trends (errors per 1000 words; null density when no writing volume),
  LLM practice generation (202).
- Frontend: /learning Center — review cards (Chinese → English → feedback →
  next), summary stats, weakness list; nav link.
- Tests: 8 SM-2 unit + 9 learning integration + 3 E2E.

Out of scope (next): IELTS (6), evaluations/rewrites as post-writing actions
(7), outlines/LangGraph (8), learning plans/tasks + analytics (9), billing
(10), production readiness (11).

## 3l. Slice 6 — IELTS question bank (2026-11-15)

**Status: DONE, verified, committed.** Backend 282 pytest passed (18 new IELTS
+ 1 contract), Playwright **51 passed** (4 new), vitest 21, tsc/ESLint/build/
ruff clean. Migration 0012 applied. Contract operations 59/88 (total corrected
from 87: the 3UX accept operation had never been counted).

Scope delivered:

- Migration 0012: ielts_questions (task_type/license_status/source_type CHECKs,
  publication flag), question_tags (unique name/slug), ielts_question_tags
  (composite PK), user_favorite_questions (composite PK user+question);
  deferred essays.question_id FK attached. Idempotent uuid5 seed applied
  online; offline --sql mode emits DDL only (regression-tested).
- 60 original licensed-safe questions (ADR-018, R12): 18 Task 1 Academic
  (6 chart types × 3, text-based data), 9 GT letters (3 registers × 3),
  33 Task 2 (5 question types), 18 topic tags, Chinese translations.
- API (6 ops): GET /ielts/questions (keyset pagination; task_type/topic/
  question_type filters), GET /ielts/questions/{id}, GET /ielts/questions/
  random, GET /ielts/tags (published counts), POST/DELETE favorite
  (idempotent, user-scoped). Published+license gate enforced in the
  repository for every read path.
- Essay binding: question_id existence + permission check, writing_type/task
  consistency (422 on mismatch), question_prompt autofill from the bank.
- Frontend: /ielts page — filters, question cards, favorite toggle, random,
  detail view with translation + source/license line, Start writing → essay
  bound to the question (editor question section, ADR-016). Nav link.
- E2E DB prep (scripts/prepare_e2e_db.py) re-seeds the bank: the pytest suite
  shares ai_writing_coach_test and truncates per test, which previously left
  the E2E bank empty.
- Tests: 18 IELTS integration (gate, filters, pagination, favorites,
  ownership, essay binding, seed idempotency) + contract coverage test;
  4 E2E (browse/filter, favorite persistence, random detail, start-writing).

Out of scope (next): evaluations/rewrites as post-writing actions (7),
outlines/LangGraph (8), learning plans/tasks + analytics (9), billing (10),
production readiness (11).

## 3m. Slice 7 — Evaluations & rewrites (2026-11-15)

**Status: DONE, verified, committed.** Backend 302 pytest passed (19 new
evaluations + 1 contract), Playwright **54 passed** (3 new), vitest 21,
tsc/ESLint/build/ruff clean. Migration 0013 applied. Contract operations
66/88.

Scope delivered:

- Migration 0013: essay_evaluations (same-essay composite FK to
  essay_versions, status/type CHECKs, is_estimate default true), essay_rewrites
  (source-matches-evaluation composite FK, level/status CHECKs, cascade from
  evaluation), essay_edit_events.rewrite_id + accept_rewrite event type.
- Queue endpoints return 202; LLM work runs in FastAPI BackgroundTasks with
  the app session factory (test-isolated), outside DB transactions (ADR-019).
- IELTS Task 1 / Task 2 / general evaluation schemas + versioned prompts;
  half-band normalization and server-computed overall band; estimate badge;
  usage logging for success and failure; failed rows keep error_message.
- Rewrites level_1–4 (meaning-preserving prompt contract), server-stored
  result text + change_summary; atomic accept: revision check (409), working
  document update, ai_rewrite version, result_version_id, accept_rewrite edit
  event; duplicate accept 409; Original untouched; client never supplies text.
- Idempotency-Key on queue/rewrite/accept (replay without re-execution).
- Frontend: Evaluate toolbar button → dialog (checkpoint → evaluate → poll;
  band/criteria/Chinese feedback; history + delete; rewrite level picker,
  preview, explicit accept applying content + revision to the editor).
- Tests: 19 integration (lifecycle, schemas, normalization, failure path,
  ownership, idempotency, atomic accept, conflicts, cascade) + 3 E2E.

Out of scope (next): outlines/LangGraph (8), learning plans/tasks + analytics
(9), billing (10), production readiness (11).

## 3n. Slice 8 — Outlines & LangGraph workflows (2026-11-15)

**Status: DONE, verified, committed.** Backend 322 pytest passed (9 outline +
10 workflow + 1 contract new), Playwright **57 passed** (3 new), vitest 21,
tsc/ESLint/build/ruff clean. Migration 0014 applied. Contract operations
79/88. New dependency: langgraph 1.x (SD §9 requirement).

Scope delivered:

- Migration 0014: writing_outlines (status lifecycle, UNIQUE(essay, version),
  same-owner composite FK, workflow link), outline_nodes (section→paragraph→
  sentence_idea self-FK hierarchy, cascade), workflows (business status,
  input/result JSON), workflow_events (append-only).
- Outlines API (8 ops): 202 background generation with semantic recall of
  learned expressions; draft-only thesis edit + node CRUD; confirmation lock;
  ownership enforced everywhere.
- LangGraph StateGraphs: writing_planner (retrieve→generate→quality-check
  conditional loop), learning_extractor (extract→dedupe), study planner
  (gather weakness/mastery context→plan). Durable pause/resume via PG
  business state; confirm applies through business services (confirmed
  outline / KB saves with duplicate skip); revise re-runs; cancel; events
  never expose graph internals (ADR-020).
- Ghost text (FR-10.4): confirmed-plan idea hint bar; insertion only on
  explicit Insert click; Tab stays reserved for grammar acceptance.
- Frontend: Plan toolbar button + planner dialog (viewpoint → generate →
  review tree → edit thesis → confirm); confirmed plan rendered in the left
  outline panel; study-planner card on /learning (goal → generate → confirm/
  reject) exercising the workflow API.
- Tests: 19 integration (hierarchy, lifecycle, ownership, cascade, failure,
  workflow resume/reject/revise/cancel, extractor save, events) + 3 E2E.

Out of scope (next): learning plans/tasks + analytics + preferences (9),
billing (10), production readiness (11).

## 3o. Slice 9 — Preferences, plans/tasks, analytics (2026-11-15)

**Status: DONE, verified, committed. FULL CONTRACT COVERAGE: 88/88.**
Backend 336 pytest passed (4 preferences + 5 plans/tasks + 4 analytics + 1
contract new), Playwright **60 passed** (3 new), vitest 21, tsc/ESLint/build/
ruff clean. Migration 0015 applied.

Scope delivered:

- Preferences: GET/PATCH /users/me/preferences — typed merge-patch over
  user_profiles.preferences (auto_grammar_check, auto_expression_assist,
  daily_review_goal, ui_language); unknown keys rejected; level/band/variant
  remain profile columns via /users/me.
- Migration 0015: learning_plans (status + daily-target CHECKs),
  learning_tasks (type/status CHECKs, same-owner composite FK for
  related_expression_id, plan FK SET NULL, question FK to the public bank).
- Plans/tasks API: POST/GET plans, GET tasks, PATCH task (completion stamps
  completed_at; reopen clears it). Study-planner workflow confirmation now
  creates a plan + one pending task per suggestion (deterministic; SM-2 keeps
  review timing — SD §9.3).
- Analytics API: user-scoped totals (calls/success/error/tokens/cost),
  per-feature breakdown, zero-filled 14-day cost/call trends.
- Frontend: preferences card (optimistic updates) + AI usage card (totals,
  features, trend bars) on /profile; plans & tasks card on /learning with
  one-click completion; planner confirm refreshes plans/tasks.
- Tests: 13 integration + 3 E2E. Fixed a controlled-checkbox race (async
  mutation reverted the DOM state) with optimistic cache updates + rollback.

Remaining: additive contract extensions R7 (password reset), R8 (billing),
R9 (account deletion/export); Slice 10 commercialization; Slice 11
production readiness.

## 3p. Slice 10 — Commercialization (sandbox) (2026-11-15)

**Status: DONE, verified, committed. Contract 1.3.0: 95/95 operations.**
Backend 350 pytest passed (13 billing + 1 contract new), Playwright
**62 passed** (2 new), vitest 21, tsc/ESLint/build/ruff clean. Migration 0016
applied.

Scope delivered:

- Contract 1.3.0 (additive, R8 resolved): GET /billing/plans, /subscription,
  /history, /usage; POST /billing/checkout, /confirm, /cancel.
- Migration 0016: subscription_plans (seeded free/pro/ultimate, deterministic
  ids), user_subscriptions (UNIQUE user, lifecycle statuses), usage_meters
  (UNIQUE user+month, non-negative counters), payment_transactions (provider
  CHECK 'sandbox' — real activation gated on user approval).
- Quotas: guards immediately before every synchronous LLM call site and at
  queue time for background flows; 429 QUOTA_EXCEEDED. Metering centralized
  in llm.record_usage (rule-only checks consume nothing, SD §12.4); atomic
  upserts + increments (fixed a concurrent-creation race found by E2E).
- Lifecycle: lazy free tier; sandbox checkout → confirm activates; cancel
  keeps access until period end then rolls to free; calendar-month periods;
  Idempotency-Key on checkout/confirm.
- Frontend: /billing page (plan cards, sandbox upgrade, quota usage, cancel,
  history) + nav link.
- Tests: 13 integration (plans, upgrade, validation, ownership, cancel,
  metering, both quotas, upgrade-lifts-quota, scoping, idempotency, auth) +
  2 E2E. ADR-021.

Remaining: R7 password reset + R9 account deletion/export and Slice 11
production readiness (deployment, backup/recovery, monitoring, CI/CD,
security review, performance + AI quality reports).

## 3q. Slice 11a — Privacy: reset, deletion, export (2026-11-15)

**Status: DONE, verified, committed. Contract 1.4.0: 99/99 operations.
R7/R8/R9 all resolved.** Backend 361 pytest passed (6 reset + 4 privacy + 1
contract new), Playwright **65 passed** (3 new), vitest 21, tsc/ESLint/build/
ruff clean. Migration 0017 applied.

Scope delivered:

- Password reset (R7): request always 202 (no enumeration); hashed single-use
  tokens, 60-min TTL; confirm updates password + revokes all sessions;
  rate-limited; email via provider abstraction (console dev-only; real
  provider activation user-gated, launch-blocking). Migration 0017.
- Account deletion (R9): DELETE /users/me — full FK-safe cascade in one
  transaction (essay version pointers cleared first), system reference data
  preserved; authenticated self-service.
- Data export (R9): GET /users/me/export — complete JSON of owned data,
  never password hashes or refresh tokens.
- Frontend: /forgot-password, /reset-password (token from query), login
  "Forgot password?" link, profile Data & privacy card (JSON download +
  two-step confirmed deletion).
- Tests: 10 integration + 3 E2E. ADR-022. Fixed duplicate YAML /users/me key
  (contract) and test identity-map caching.

Remaining (Slice 11b): production readiness — deployment config,
backup/recovery, structured logging/monitoring, rate-limit hardening, CI/CD,
security review, performance + AI quality evaluation reports, launch
checklist (real email + LLM keys + payment activation are user-gated).

## 3r. Slice 11b — Production readiness (2026-11-15)

**Status: DONE, verified, committed. All engineering launch items complete;
only user-gated blockers remain (LAUNCH_CHECKLIST.md).**

Scope delivered (previous session implemented; takeover session verified,
fixed gaps and committed):

- Observability: structured JSON access logs + `X-Request-ID` tracing
  (echo/generate), duration_ms, no bodies/tokens/cookies/keys ever logged;
  health at DEBUG (`app/core/logging.py`, 4 tests).
- Hardening: general per-IP sliding-window API rate limit (default 300/min,
  0 disables) alongside the stricter auth limiter; single storage point for
  future shared-store swap. Limiter trip observed live during perf probing.
- Deployment: non-root backend/frontend Dockerfiles, `.dockerignore` (added
  in takeover — secrets/build artifacts excluded from images), production
  compose (only nginx exposed; config validated), nginx security headers,
  `.env.production.example`. Image builds deferred to approved deployment.
- Backup/recovery: `backup_db.py` / `restore_db.py` (live-DB restore refuses
  without `--force`) / `verify_backup.py`; round-trip re-verified: 40 tables,
  identical row counts, scratch DB auto-dropped.
- CI: GitHub Actions backend (ruff+pytest+pip-audit), frontend
  (eslint/tsc/vitest/build+npm prod audit), E2E (chromium via
  PLAYWRIGHT_CHANNEL; local keeps Edge). Audits added in takeover.
- Verification: perf probe re-run (30 samples/endpoint, worst P95 60.1 ms <
  500 ms); pip-audit clean (venv pip upgraded 25.2→26.3); npm production
  audit clean; 8 moderate dev-only lint advisories documented as accepted
  risk; mock AI eval harness re-validated (15 calls, 0 errors — pipeline
  evidence only). Full regression: backend **362 passed**, Playwright
  **65 passed** (3.7 m), vitest 21, tsc/ESLint/build/ruff clean.
- Takeover-session defect fixes: httpx was dev-only while app code imports
  it at runtime (production image would crash) — moved to main dependencies
  + `tests/test_runtime_dependencies.py` guard; Playwright config and
  global-setup hardcoded the Windows venv path — made cross-platform for
  Linux CI; CI docker build-only job added because Docker Hub is unreachable
  from the dev machine.
- Docs: DEPLOYMENT, BACKUP_RECOVERY, SECURITY_REVIEW, PERFORMANCE_REPORT,
  AI_QUALITY_REPORT, LAUNCH_CHECKLIST, ADR-023.

**Blocked on user (launch-gated, unchanged):** rotated DeepSeek key
(`LLM_API_KEY` empty — real AI quality evaluation), real embedding endpoint,
real email provider, real payment activation, production secrets + TLS,
public deployment approval.

## 3s. ADR-024 — 对话式构思 + 悬浮直显反馈 + 中文界面 (2026-11-15)

**Status: DONE, verified, committed. User-directed interaction overhaul.**

诊断（用户报告"语法检查失效/详解连不上大模型/Tab 用不了"）：
- 语法检查前后端均要求活动写作会话；用户未手动启动会话 → 检查从未触发，
  teaching 请求也从未发出（ai_usage_logs 无 teaching 记录）。LLM 本身正常
  （同日 outline_generate/general_evaluate 均 success）。
- Tab 仅在点击模糊答案 pin 后生效，交互不可发现。

交付：
- 打开编辑器自动创建辅助会话（显式取消后不重建；提交后继续写作会重建）。
- 悬浮卡直显推荐修改 + 内嵌情境讲解（reveal/teaching 并行拉取，服务端缓存）；
  Tab 卡片可见即接受；移除模糊/点击揭示/教学图标/点击错误触发讲解。
- 左侧对话式构思：POST/GET /essays/{id}/planner/chat|messages（契约 1.5.0，
  101 操作），outline_chat_messages（迁移 0018），planner_chat v1 +
  outline_generate v2（中文指引、英文 thesis）；确认归档旧计划；移除 Plan
  按钮与文档大纲树。
- 光标处灰色中文 inline 指引（ProseMirror widget，不持久化/不计字数/不代写）。
- 全站简体中文 UI（作文正文/题目/IELTS 题干保留英文）。
- 测试：backend 369 passed（+7 planner chat +1 依赖守卫），Playwright 66，
  vitest 21，tsc/ESLint/build/ruff clean。mock planner 确定性 propose 供 E2E。
- 文档：ADR-024、AGENTS.md §4 Editor UX 修订、TRACEABILITY_MATRIX 变更日志。

环境事件：E2E 期间 Docker Desktop 崩溃，`docker desktop restart` 恢复后重跑。

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