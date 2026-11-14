# AI Writing Coach — Requirement Traceability Matrix

**Created:** 2026-11-15 (Master Development Directive V2.0, §1)
**Maintained by:** every implementation slice must update this file.
**Baselines:** PRD V1.1 (DOCX) · System Design V1.1 · Database ERD V1.2 · API Specification V1.1.1 · `contracts/openapi.yaml` (OpenAPI 3.1, info.version 1.1.1)

Status legend:

- **IV** — Implemented and verified (automated tests executed and passing; date recorded).
- **IU** — Implemented but not fully verified (code exists; verification gap named).
- **NI** — Not implemented.

Verification evidence root: backend `pytest` (real PostgreSQL `ai_writing_coach_test`), frontend `tsc`/ESLint/`next build`, Playwright E2E (isolated stack :8001/:3600, Edge channel).

## 1. Document reconciliation record

Contradictions found between baselines, and their resolutions. Original documents are
authoritative starting references; resolutions below are the adopted engineering decisions
(Directive V2.0 §1 allows improving defective designs with documentation sync).

| # | Conflict | Resolution | Synced docs |
|---|---|---|---|
| R1 | PRD FR-02.4 says detailed teaching should prefer a pre-built teaching template library; System Design §5.5/ADR-015, AGENTS.md and Directive §3.5 forbid a generic reusable teaching library | **Contextual-only teaching wins** (later, explicitly confirmed decision). Teaching is generated for the user's current sentence/context; cache only for same user+issue+revision+context_hash. PRD DOCX preserved unchanged as historical baseline | This matrix; AGENTS.md already aligned |
| R2 | PRD §4.2 sketches a right-side AI panel; confirmed layout (Directive §3.2, SD §1.1/§3.2, AGENTS) is inline-first with collapsible left outline, no permanent right panel | **Inline-first wins.** Feedback appears around the original text; floating cards on demand; bottom sheets on narrow screens | This matrix |
| R3 | Contract `SnapshotCreate` accepts `label`; ERD V1.2 `essay_versions` has no label column | **Add nullable `label VARCHAR(255)`** to `essay_versions` (migration 0004); ERD §6.4 updated | ERD, migration 0004 |
| R4 | `essays.status` / `users.status` CHECK values were provisional bootstrap decisions; ERD does not enumerate them | **Adopt** `essays.status ∈ {active, archived}`, `users.status ∈ {active, disabled}`; recorded in ERD as the approved enumeration | ERD §5.1/§6.1 |
| R5 | PRD §10 conceptual entity list (EssayQuestion, EssayFeedback, WritingError, ErrorRule, Expression, Subscription…) differs from ERD V1.2's 29 entities | ERD V1.2 is the refined schema baseline (PRD §10 explicitly defers fields to ERD stage). Mapping: WritingError→`writing_issues`, EssayFeedback→`essay_evaluations`, UserExpression→`user_expressions`. `ErrorRule` stays as code-level rule metadata (no table needed initially). **Subscription/billing entities are absent from ERD** — added in the commercialization phase (see G3) | This matrix; ERD when billing lands |
| R6 | `docs/README.md` and `DEVELOPMENT_PLAN.md` recorded System Design V1.1 as MISSING | **Stale.** User supplied `docs/AI_Writing_Coach_System_Design_V1.1.md` (959 lines); committed in `7baeb36`. Both docs updated | docs/README.md, DEVELOPMENT_PLAN.md |
| R7 | PRD FR-01 requires password reset; contract has no reset endpoints | **Gap.** Additive contract addition planned (auth hardening slice): request-reset + confirm-reset with hashed single-use tokens; email delivery behind a provider abstraction (real SMTP/provider activation needs approval per Directive §6) | Contract + API Spec when implemented |
| R8 | Directive §H + PRD G5/V1.4 require subscriptions/quotas/billing; contract and ERD have none | **Gap.** Design + additive contract/ERD additions in commercialization phase. Payment provider runs in sandbox/mock until user authorizes real activation (Directive §6/§10) | Contract + ERD + ADR when implemented |
| R9 | Directive §I requires account deletion + data export; PRD §9.3 privacy controls; contract only has per-resource deletes | **Gap.** Additive endpoints planned (privacy slice): full account deletion cascade + JSON export of user data | Contract + API Spec when implemented |
| R10 | `Idempotency-Key` accepted by contract but dedup storage not implemented | **Resolved in Slice 2B**: `idempotency_keys` table (migration 0004) + `app/core/idempotency.py`; applied to POST snapshots; reused by submit/evaluations/rewrites in later slices. Concurrent in-flight repeats get 429; stale placeholders reclaimed after 60s | DEVELOPMENT_PLAN.md, ERD §0 |
| R11 | Frontend API types are hand-mirrored (`src/types/api.ts`), not generated; contract uses YAML anchors | **Resolved in Slice 2C**: `npm run generate:api` (scripts/generate-api-types.mjs) resolves anchors via the yaml package and emits `src/types/generated.ts` (15 contract schemas); api.ts re-exports them. Open response bodies stay hand-mirrored | frontend README, scripts |
| R12 | PRD FR-08.5 wants 200–300 verified, licensed IELTS questions; copyright constraints | Seed with **original practice questions** (PRD explicitly permits) covering all Task 1/2 types and topics; `license_status` gates any third-party content; no unlicensed Cambridge replication | IELTS seed data + ADR |

## 2. Feature traceability (PRD → design → schema → API → code → tests)

| PRD requirement | SD module | ERD entities | API endpoints | Backend status | Frontend status | Tests / evidence |
|---|---|---|---|---|---|---|
| FR-01 register/login | Auth | users, auth_sessions, auth_refresh_tokens | POST /auth/register, /auth/login | **IV** 2026-11-15 | **IV** login/register pages | 55 auth tests; E2E auth 11 |
| FR-01 JWT + refresh lifecycle, device sessions | Auth | auth_sessions, auth_refresh_tokens | refresh/logout/logout-all/sessions GET/DELETE | **IV** 2026-11-15 | **IV** single-flight refresh, silent restore | reuse-revocation, concurrency, cookie-attribute tests |
| FR-01 password reset | Auth | (reset tokens — to add) | (R7 gap) | **NI** | **NI** | — |
| FR-01 profile management | Users | user_profiles | GET/PATCH /users/me | **IV** 2026-11-15 | **IV** /profile | auth tests + E2E |
| FR-01 preferences (level, target band, variant, toggles) | Users | user_profiles.preferences | GET/PATCH /users/me/preferences | **NI** | **NI** | — |
| FR-01 data isolation | all | all private tables | all private APIs | **IV** (auth+essays scope; extends per slice) | n/a | ownership tests per module |
| FR-02.1 create/edit essay | Essays | essays | POST/GET /essays, GET/PATCH/DELETE /essays/{id} | **IV** 2026-11-15 | **IV** /dashboard, /essays/[id] | 16 essay tests; E2E essays 7 |
| FR-02.1 autosave + manual save | Essays | essay_working_documents | GET/PUT /essays/{id}/working-document | **IV** 2026-11-15 (Slice 2B) | **IV** 2026-11-15 (Slice 2C: debounced autosave, Ctrl+S, save status, conflict recovery) | 13 working-document integration tests; E2E autosave/reload/conflict |
| FR-02.1 undo/redo, word count | Editor | — | — | n/a | **IV** 2026-11-15 (TipTap StarterKit history; word count mirrors server rule) | E2E undo/redo + word count; 12 unit tests |
| FR-02.1 history versions | Essays | essay_versions | GET versions, GET versions/{id} | **IV** 2026-11-15 (Slice 2B) | **IV** 2026-11-15 (history dialog, read-only view) | version tests; E2E checkpoint/restore |
| FR-11 snapshots/restore | Essays | essay_versions, essay_edit_events | POST snapshots, POST restore | **IV** 2026-11-15 (Slice 2B; migration 0004) | **IV** 2026-11-15 (checkpoint creation + confirmed restore) | 16 version/restore tests; E2E restore flow |
| FR-11.2 edit events | Essays | essay_edit_events | (internal to atomic ops) | **IV** 2026-11-15 (restore events; more event types with later slices) | n/a | restore event assertions |
| FR-13 / SD §10 writing modes + sessions | Writing Sessions | writing_sessions | POST/GET /essays/{id}/sessions, GET/PATCH /writing-sessions/{id}, POST submit | **NI** (Slice 2D; migration 0004) | **NI** | — |
| FR-02.2–.7 rule-first grammar check | Grammar | writing_issues, issue_suggestions | POST grammar-check, GET issues, GET issues/{id} | **NI** | **NI** | — |
| FR-02.4 self-correction validation | Grammar | writing_issues, essay_edit_events | POST issues/validate | **NI** | **NI** | — |
| FR-02.4 reveal / ignore | Grammar | issue_suggestions | POST reveal, PATCH issues/{id} | **NI** | **NI** | — |
| FR-02.4 contextual teaching (R1) | Teaching | issue_teachings | POST issues/{id}/teaching | **NI** | **NI** | — |
| FR-02.8 expression polish | Expressions | (suggestion records) | POST expression-suggestions, POST accept | **NI** | **NI** | — |
| FR-03 Chinese→English | Expressions | — | POST translations | **NI** | **NI** | — |
| FR-04 knowledge base CRUD | Expressions | user_expressions, expression_sources | POST/GET /expressions, GET/PATCH/DELETE /expressions/{id}, POST archive | **NI** | **NI** | — |
| FR-04.5 extraction w/ confirmation | Workflows | user_expressions | POST /essays/{id}/expressions/extract | **NI** | **NI** | — |
| FR-04.6 search (keyword/semantic) | Knowledge | expression_embeddings | POST /expressions/search | **NI** | **NI** | — |
| FR-05 translation exercises + SM-2 | Learning | expression_progress, expression_reviews | GET /learning/reviews/due, POST /learning/reviews, GET progress | **NI** | **NI** | — |
| FR-06 previously-learned recommendations | Knowledge | user_expressions, expression_embeddings | (within expression-suggestions) | **NI** | **NI** | — |
| FR-07 weakness profile + trends | Learning | user_weaknesses | GET weaknesses, /{category}, /trends, POST practice | **NI** | **NI** | — |
| FR-08 IELTS question bank | IELTS | ielts_questions, question_tags, ielts_question_tags, user_favorite_questions | GET questions/{id}/random/tags, POST/DELETE favorite | **NI** | **NI** | — |
| FR-09 IELTS evaluation (4 criteria, estimates) | Evaluations | essay_evaluations | POST/GET /essays/{id}/evaluations, GET/DELETE /evaluations/{id} | **NI** | **NI** | — |
| FR-09.3 rewrite levels 1–4 + accept | Evaluations | essay_rewrites | POST rewrite, GET /rewrites/{id}, POST accept | **NI** | **NI** | — |
| FR-10 writing planner / outline | Workflows | writing_outlines, outline_nodes | POST outlines/generate, GET/PATCH outlines, confirm, nodes CRUD | **NI** | **NI** | — |
| FR-10.4 Ghost Text | Editor | — | (outline-driven) | n/a | **NI** | — |
| FR-12 personalized learning plans | Learning | learning_plans, learning_tasks | POST/GET plans, GET tasks, PATCH tasks/{id}, GET /learning/summary | **NI** | **NI** | — |
| SD §9 LangGraph workflows (planner/extractor/study planner) | Workflows | (workflow state tables — to add) | POST /workflows, GET/{id}, resume, cancel, events | **NI** | **NI** | — |
| SD §12.4 AI cost logging | Analytics | ai_usage_logs | GET /analytics/ai-usage, by-feature, trends | **NI** | **NI** | — |
| G5 / Directive H subscriptions, quotas, billing | (new module) | (R8 gap — to add) | (R8 gap — to add) | **NI** | **NI** | — |
| Directive I production readiness (deploy, backup, monitoring, CI/CD, privacy) | Infrastructure | — | (R9 gap partially) | **NI** (Docker Compose dev stack exists) | **NI** | — |
| Infrastructure health | Health | — | GET /health | **IV** 2026-11-15 | **IV** landing health chip | 3 smoke + 2 integration + E2E |

## 3. Contract operation inventory (87 operations)

Verified 2026-11-15 by script comparing `contracts/openapi.yaml` paths against the
FastAPI-generated OpenAPI: **21 implemented, 66 missing, 0 out-of-contract routes**
(15 at baseline; +6 in Slice 2B). Enforced permanently by
`tests/test_contract.py::test_no_out_of_contract_routes`.

### Implemented (21) — all IV

| Method | Path | Slice |
|---|---|---|
| GET | /health | Stage 1 |
| POST | /auth/register | 1 |
| POST | /auth/login | 1 |
| POST | /auth/refresh | 1 |
| POST | /auth/logout | 1 |
| POST | /auth/logout-all | 1 |
| GET | /auth/sessions | 1 |
| DELETE | /auth/sessions/{session_id} | 1 |
| GET | /users/me | 1 |
| PATCH | /users/me | 1 |
| POST | /essays | 2A |
| GET | /essays | 2A |
| GET | /essays/{essay_id} | 2A |
| PATCH | /essays/{essay_id} | 2A |
| DELETE | /essays/{essay_id} | 2A |
| GET | /essays/{essay_id}/working-document | 2B |
| PUT | /essays/{essay_id}/working-document | 2B |
| POST | /essays/{essay_id}/snapshots | 2B |
| GET | /essays/{essay_id}/versions | 2B |
| GET | /essays/{essay_id}/versions/{version_id} | 2B |
| POST | /essays/{essay_id}/restore | 2B |

### Missing (66) — grouped by planned slice

| Slice | Operations |
|---|---|
| 2D Writing sessions | POST/GET /essays/{id}/sessions; GET/PATCH /writing-sessions/{id}; POST submit (5) |
| 3 Grammar core | POST grammar-check; GET issues; GET issues/{id}; POST issues/validate; PATCH issues/{id}; POST reveal (6) |
| 3 Teaching | POST issues/{id}/teaching (1) |
| 4 Expressions & translation | POST expression-suggestions; POST accept; POST translations; POST/GET /expressions; GET/PATCH/DELETE /expressions/{id}; POST archive; POST search; POST extract (10) |
| 5 Learning & weakness | GET reviews/due; POST reviews; GET progress; GET summary; POST/GET plans; GET tasks; PATCH tasks/{id}; GET weaknesses; GET weaknesses/{category}; GET trends; POST practice (12) |
| 6 IELTS | GET questions; GET questions/{id}; GET tags; GET random; POST/DELETE favorite (6) |
| 7 Evaluations & rewrites | POST/GET evaluations; GET/DELETE /evaluations/{id}; POST rewrite; GET /rewrites/{id}; POST accept (7) |
| 8 Outlines | POST generate; GET outlines; GET/PATCH /outlines/{id}; POST confirm; POST nodes; PATCH/DELETE nodes/{id} (7) |
| 9 Workflows | POST /workflows; GET/{id}; POST resume; POST cancel; GET events (5) |
| 10 Analytics | GET ai-usage; GET by-feature; GET trends (3) |
| 1 Users preferences | GET/PATCH /users/me/preferences (2) |
| Later additive (R7/R8/R9) | password reset, billing/quotas, account deletion/export — not yet in contract |

(5+6+1+10+12+6+7+7+5+3+2 = 64; plus 2 preferences counted above = 66 total.)

## 4. ERD entity inventory (29 entities)

| Entity | Migration | Status |
|---|---|---|
| users | 0002 | **IV** |
| user_profiles | 0002 | **IV** |
| auth_sessions | 0002 | **IV** |
| auth_refresh_tokens | 0002 | **IV** |
| essays | 0003 | **IV** |
| essay_working_documents | 0003 | **IV** (autosave + optimistic concurrency, Slice 2B) |
| essay_versions | 0003 + 0004 label | **IV** (snapshots/versions/restore, Slice 2B) |
| writing_sessions | 0005 (planned, Slice 2D) | **NI** |
| essay_edit_events | 0004 | **IV** (restore events; further event types with later slices) |
| writing_issues | phase B | **NI** |
| issue_suggestions | phase B | **NI** |
| issue_teachings | phase B | **NI** |
| essay_evaluations | phase B | **NI** |
| essay_rewrites | phase B | **NI** |
| user_expressions | phase B | **NI** |
| expression_sources | phase B | **NI** |
| expression_embeddings | phase B | **NI** |
| expression_progress | phase B | **NI** |
| expression_reviews | phase B | **NI** |
| user_weaknesses | phase B | **NI** |
| ielts_questions | phase C | **NI** |
| question_tags | phase C | **NI** |
| ielts_question_tags | phase C | **NI** |
| user_favorite_questions | phase C | **NI** |
| writing_outlines | phase C | **NI** |
| outline_nodes | phase C | **NI** |
| learning_plans | phase C | **NI** |
| learning_tasks | phase C | **NI** |
| ai_usage_logs | phase C | **NI** |

## 5. Verification deliverables (Directive §8/§11) — status

| Deliverable | Status |
|---|---|
| Backend unit/integration/transaction/ownership/concurrency/migration/contract tests | **IV** for implemented scope (94 tests, 2026-11-15); grows per slice |
| Frontend tsc/ESLint/build + Playwright E2E | **IV** for implemented scope (18 E2E, 2026-11-15) |
| Grammar precision/recall/false-positive evaluation set | **NI** (with Grammar slice) |
| Correction validity / teaching quality / translation quality evals | **NI** (with LLM slices) |
| RAG Recall@K / MRR evaluation | **NI** (with Knowledge slice) |
| IELTS evaluation consistency + rewrite semantic preservation | **NI** (with Evaluations slice) |
| Prompt/model version tracking | **NI** (with LLM layer) |
| Latency/token cost reports | **NI** (ai_usage_logs + analytics) |
| Performance report (P95 < 500ms non-AI) | **NI** |
| Security assessment | **NI** (auth design verified by tests; full review before launch) |
| Backup/recovery verification | **NI** |
| Subscription sandbox tests | **NI** |
| AI cost model / gross-margin analysis | **NI** |
| Deployment guide | **NI** (dev Docker Compose exists) |

## 6. Change log

| Date | Change |
|---|---|
| 2026-11-15 (Slice 2C) | TipTap writing editor live on /essays/[id]: debounced autosave + Ctrl+S + save status + conflict recovery (keep local / copy / load latest), word count, undo/redo, formatting toolbar, collapsible left outline (expanded by default), version history dialog with checkpoints + confirmed restore, IME-composition-safe saving. Unicode codepoint↔UTF-16↔ProseMirror mapping utilities with 12 unit tests. OpenAPI type generation pipeline (R11). Verification: Playwright **25 passed** (7 new editor tests), vitest 12 passed, tsc/ESLint/build clean. Fixed real defects: toolbar no-op on fresh unfocused editor; descendants() pruning in position mapping; E2E rate-limit exhaustion (E2E-only env relaxation). `awc-screenshots.mjs` review utility recreated. |
| 2026-11-15 (Slice 2B) | Working Document GET/PUT, snapshots, versions, restore implemented + verified: backend **144 passed** (50 new), ruff clean. Migration 0004 (essay_edit_events, essay_versions.label, idempotency_keys). Fixed two real defects found by tests: stale identity-map read under FOR UPDATE (populate_existing) and unreliable ON CONFLICT rowcount (RETURNING). ERD V1.2.1 increments recorded. Contract operations 21/87. |
| 2026-11-15 | Matrix created from full document review + live repository audit. Baseline re-verified: pytest 94 passed, ruff/tsc/ESLint/build clean, Playwright 18 passed. Slice 2A committed as `7baeb36`. Reconciliations R1–R12 recorded. |
