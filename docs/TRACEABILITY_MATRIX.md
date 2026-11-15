# AI Writing Coach — Requirement Traceability Matrix

**Created:** 2026-11-15 (Master Development Directive V2.0, §1)
**Maintained by:** every implementation slice must update this file.
**Baselines:** PRD V1.1 (DOCX) · System Design V1.1 · Database ERD V1.2 · API Specification V1.1.1 · `contracts/openapi.yaml` (OpenAPI 3.1, info.version 1.2.0)

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
| R12 | PRD FR-08.5 wants 200–300 verified, licensed IELTS questions; copyright constraints | Seed with **original practice questions** (PRD explicitly permits) covering all Task 1/2 types and topics; `license_status` gates any third-party content; no unlicensed Cambridge replication | IELTS seed data + ADR-018 (Slice 6) |

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
| FR-13 / SD §10 writing modes + sessions | Writing Sessions | writing_sessions | POST/GET /essays/{id}/sessions, GET/PATCH /writing-sessions/{id}, POST submit | **IV** 2026-11-15 (Slice 2D; migration 0005; server-derived enabled_features; atomic submit with Final Snapshot + shared-original case) | **IV** 2026-11-15 (mode picker, exam countdown, submit/cancel controls) | 14 session integration tests incl. DB-level same-owner FK; 5 session E2E tests |
| FR-02.2–.7 rule-first grammar check | Grammar | writing_issues, issue_suggestions | POST grammar-check, GET issues, GET issues/{id} | **IV** 2026-11-15 (Slice 3: LanguageTool 6.6 + custom rules, classification, Chinese short explanations, LLM only for uncertain fragments, codepoint offsets, masked answers) | **IV** 2026-11-15 (category-colored underlines, inline hints, debounced checks, stale-result discard) | 13 check integration tests vs real LT; 9 rule unit tests; 7 grammar E2E |
| FR-02.4 self-correction validation | Grammar | writing_issues, essay_edit_events | POST issues/validate | **IV** 2026-11-15 (atomic, rule-first re-check, accepts valid alternatives, re-anchors on incorrect, LLM judgement outside transaction) | **IV** 2026-11-15 (auto-validate after save; correct clears highlight) | 6 validation integration tests; E2E correct/incorrect flows |
| FR-02.4 reveal / ignore | Grammar | issue_suggestions | POST reveal, PATCH issues/{id} | **IV** 2026-11-15 (reveal returns full suggestions only on explicit request) | **IV** 2026-11-15 (blurred •••• until Reveal; Alt+R/T/I shortcuts) | reveal/ignore tests; E2E blurred-answer assertions |
| FR-02.4 contextual teaching (R1) | Teaching | issue_teachings | POST issues/{id}/teaching | **IV** 2026-11-15 pipeline (context-hash cache, usage logging, personalized_note null without verified history); **IU** linguistic quality — mock provider until LLM keys configured | **IV** 2026-11-15 (floating teaching card near the error) | 5 teaching integration tests; E2E card flow |
| SD §7 LLM provider abstraction | AI layer | ai_usage_logs | (internal) | **IV** 2026-11-15 (mock + OpenAI-compatible adapter, Pydantic-validated outputs, versioned prompts, full usage/cost logging); real-provider activation awaits user keys | n/a | 7 AI unit tests; usage-log assertions |
| FR-02.8 expression polish | Expressions | expression_suggestions (+items, ERD §9.6) | POST expression-suggestions, POST accept | **IV** 2026-11-15 (Slice 4: mode-enforced, persisted candidates, atomic server-authoritative acceptance) | **IV** 2026-11-15 (selection → floating candidates → accept → save-to-KB) | 9 assist integration tests; 4 expression E2E |
| FR-03 Chinese→English | Expressions | expression_suggestions | POST translations | **IV** 2026-11-15 (2–4 context-aware candidates, mode-enforced) | **IV** 2026-11-15 (CJK selection → translate → apply) | integration + E2E translation flow |
| FR-04 knowledge base CRUD | Expressions | user_expressions, expression_sources | POST/GET /expressions, GET/PATCH/DELETE /expressions/{id}, POST archive | **IV** 2026-11-15 (owner-scoped, dedup, soft delete, sources) | **IV** 2026-11-15 (/knowledge page) | 6 CRUD integration tests; KB E2E |
| FR-04.5 extraction w/ confirmation | Expressions | user_expressions | POST /essays/{id}/expressions/extract | **IV** 2026-11-15 (Slice 5A: immutable-version extraction, candidates returned for confirmation, nothing saved until confirmed) | **IV** 2026-11-15 (History → Extract → confirm dialog) | 3 extraction integration tests; extraction E2E |
| FR-04.6 search (keyword/semantic) | Knowledge | expression_embeddings | POST /expressions/search | **IV** 2026-11-15 keyword + semantic + hybrid (pgvector HNSW, user-scoped at query time); semantic QUALITY awaits real embedding provider | **IV** mode selector on /knowledge | 5 RAG integration tests; semantic E2E |
| FR-05 translation exercises + SM-2 | Learning | expression_progress, expression_reviews | GET /learning/reviews/due, POST /learning/reviews, GET progress | **IV** 2026-11-15 (Slice 5B: rule-first exact match, LLM semantic judging, deterministic SM-2, no answer leakage in prompts) | **IV** 2026-11-15 (/learning review flow) | 8 SM-2 unit + 9 learning integration tests; 3 learning E2E |
| FR-06 previously-learned recommendations | Knowledge | user_expressions, expression_embeddings | (within polish/translation) | **IV** 2026-11-15 pipeline: semantic recall (pgvector) with keyword fallback + LLM suitability judgment + labeling; quality awaits real embeddings | **IV** badge in candidate card | assist + RAG tests |
| FR-07 weakness profile + trends | Learning | user_weaknesses | GET weaknesses, /{category}, /trends, POST practice | **IV** 2026-11-15 (aggregation on detection, volume-adjusted weekly trends, LLM practice generation) | **IV** 2026-11-15 (weakness list on /learning) | weakness integration tests |
| FR-08 IELTS question bank | IELTS | ielts_questions, question_tags, ielts_question_tags, user_favorite_questions | GET questions/{id}/random/tags, POST/DELETE favorite | **IV** 2026-11-15 (Slice 6: 60 original licensed-safe questions covering all Task 1/2 types + 18 topics; published+license gate; essays.question_id FK attached; migration 0012) | **IV** 2026-11-15 (/ielts browse/filter/favorite/random → start writing) | 18 IELTS integration tests + contract test; 4 IELTS E2E |
| FR-09 IELTS evaluation (4 criteria, estimates) | Evaluations | essay_evaluations | POST/GET /essays/{id}/evaluations, GET/DELETE /evaluations/{id} | **IV** 2026-11-15 (Slice 7: immutable-version binding via composite FK, 202 queued + background processing, Task1/Task2/general schemas, server-computed overall band, is_estimate always true, usage logging; migration 0013) | **IV** 2026-11-15 (Evaluate dialog: band + criteria + Chinese feedback, estimate badge, history/delete) | 19 evaluation integration tests; 3 evaluation E2E |
| FR-09.3 rewrite levels 1–4 + accept | Evaluations | essay_rewrites | POST rewrite, GET /rewrites/{id}, POST accept | **IV** 2026-11-15 (Slice 7: levels 1–4, server-stored results, atomic accept with revision check + ai_rewrite version + edit event, duplicate/conflict 409, Original preserved) | **IV** 2026-11-15 (level picker, preview, explicit accept) | acceptance/conflict/duplicate/ownership integration tests; rewrite E2E |
| FR-10 writing planner / outline | Workflows | writing_outlines, outline_nodes | POST outlines/generate, GET/PATCH outlines, confirm, nodes CRUD | **NI** | **NI** | — |
| FR-10.4 Ghost Text | Editor | — | (outline-driven) | n/a | **NI** | — |
| FR-12 personalized learning plans | Learning | learning_plans, learning_tasks | POST/GET plans, GET tasks, PATCH tasks/{id}, GET /learning/summary | **NI** | **NI** | — |
| SD §9 LangGraph workflows (planner/extractor/study planner) | Workflows | (workflow state tables — to add) | POST /workflows, GET/{id}, resume, cancel, events | **NI** | **NI** | — |
| SD §12.4 AI cost logging | Analytics | ai_usage_logs | GET /analytics/ai-usage, by-feature, trends | **NI** | **NI** | — |
| G5 / Directive H subscriptions, quotas, billing | (new module) | (R8 gap — to add) | (R8 gap — to add) | **NI** | **NI** | — |
| Directive I production readiness (deploy, backup, monitoring, CI/CD, privacy) | Infrastructure | — | (R9 gap partially) | **NI** (Docker Compose dev stack exists) | **NI** | — |
| Infrastructure health | Health | — | GET /health | **IV** 2026-11-15 | **IV** landing health chip | 3 smoke + 2 integration + E2E |

## 3. Contract operation inventory (88 operations)

Verified 2026-11-15 by script comparing `contracts/openapi.yaml` paths against the
FastAPI-generated OpenAPI: **66 implemented, 22 missing, 0 out-of-contract routes**
(15 baseline; +6 2B; +5 2D; +7 3; +1 accept 3UX; +10 Slice 4; +1 extract 5A; +8 Slice 5B learning; +6 Slice 6 IELTS; +7 Slice 7 evaluations/rewrites).
Enforced permanently by `tests/test_contract.py::test_no_out_of_contract_routes`.

### Implemented (66) — all IV

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
| POST | /essays/{essay_id}/sessions | 2D |
| GET | /essays/{essay_id}/sessions | 2D |
| GET | /writing-sessions/{session_id} | 2D |
| PATCH | /writing-sessions/{session_id} | 2D |
| POST | /writing-sessions/{session_id}/submit | 2D |
| POST | /essays/{essay_id}/grammar-check | 3 |
| GET | /essays/{essay_id}/issues | 3 |
| GET | /essays/{essay_id}/issues/{issue_id} | 3 |
| POST | /essays/{essay_id}/issues/validate | 3 |
| PATCH | /essays/{essay_id}/issues/{issue_id} | 3 |
| POST | /essays/{essay_id}/issues/{issue_id}/reveal | 3 |
| POST | /essays/{essay_id}/issues/{issue_id}/accept | 3UX (contract 1.2.0) |
| POST | /essays/{essay_id}/issues/{issue_id}/teaching | 3 |
| POST | /expressions | 4 |
| GET | /expressions | 4 |
| GET | /expressions/{expression_id} | 4 |
| PATCH | /expressions/{expression_id} | 4 |
| DELETE | /expressions/{expression_id} | 4 |
| POST | /expressions/{expression_id}/archive | 4 |
| POST | /expressions/search | 4 |
| POST | /essays/{essay_id}/expression-suggestions | 4 |
| POST | /essays/{essay_id}/expression-suggestions/{suggestion_id}/accept | 4 |
| POST | /essays/{essay_id}/translations | 4 |
| POST | /essays/{essay_id}/expressions/extract | 5A |
| GET | /learning/reviews/due | 5B |
| POST | /learning/reviews | 5B |
| GET | /expressions/{expression_id}/progress | 5B |
| GET | /learning/summary | 5B |
| GET | /users/me/weaknesses | 5B |
| GET | /users/me/weaknesses/{category} | 5B |
| GET | /users/me/weaknesses/trends | 5B |
| POST | /users/me/weaknesses/practice | 5B |
| GET | /ielts/questions | 6 |
| GET | /ielts/questions/{question_id} | 6 |
| GET | /ielts/questions/random | 6 |
| GET | /ielts/tags | 6 |
| POST | /ielts/questions/{question_id}/favorite | 6 |
| DELETE | /ielts/questions/{question_id}/favorite | 6 |
| POST | /essays/{essay_id}/evaluations | 7 |
| GET | /essays/{essay_id}/evaluations | 7 |
| GET | /evaluations/{evaluation_id} | 7 |
| DELETE | /evaluations/{evaluation_id} | 7 |
| POST | /evaluations/{evaluation_id}/rewrite | 7 |
| GET | /rewrites/{rewrite_id} | 7 |
| POST | /rewrites/{rewrite_id}/accept | 7 |

### Missing (22) — grouped by planned slice

| Slice | Operations |
|---|---|
| 9 Learning plans/tasks | POST/GET /learning/plans; GET /learning/tasks; PATCH /learning/tasks/{id} (4) |
| 8 Outlines | POST generate; GET essay outlines; GET/PATCH /outlines/{id}; POST confirm; POST nodes; PATCH/DELETE nodes/{id} (8) |
| 9 Workflows | POST /workflows; GET/{id}; POST resume; POST cancel; GET events (5) |
| 10 Analytics | GET ai-usage; GET by-feature; GET trends (3) |
| 1 Users preferences | GET/PATCH /users/me/preferences (2) |
| Later additive (R7/R8/R9) | password reset, billing/quotas, account deletion/export — not yet in contract |

(4 plans/tasks + 8 outlines + 5 workflows + 3 analytics + 2 preferences = 22.)

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
| writing_sessions | 0005 | **IV** (modes, exam config, atomic submit; DB-level same-owner FK) |
| essay_edit_events | 0004 | **IV** (restore events; further event types with later slices) |
| writing_issues | 0006 | **IV** (revision-anchored, codepoint offsets, lifecycle) |
| issue_suggestions | 0006 | **IV** (server-side answers, masked until reveal) |
| issue_teachings | 0006 | **IV** (context-hash cache, contextual only) |
| essay_evaluations | 0013 | **IV** (immutable-version composite FK, estimate flag, lifecycle) |
| essay_rewrites | 0013 | **IV** (source=evaluation version FK, server-stored results, atomic accept) |
| user_expressions | 0008 | **IV** (CRUD, dedup, soft delete, statuses) |
| expression_sources | 0008 | **IV** (typed sources with ownership checks) |
| expression_embeddings | 0010 | **IV** (VECTOR(1536), HNSW cosine, rebuildable model+hash) |
| expression_progress | 0011 | **IV** (SM-2 scheduling, same-owner composite FK) |
| expression_reviews | 0011 | **IV** (answer/reference snapshot, score, feedback) |
| user_weaknesses | 0011 | **IV** (aggregated on issue detection; volume-adjusted trends) |
| ielts_questions | 0012 | **IV** |
| question_tags | 0012 | **IV** |
| ielts_question_tags | 0012 | **IV** |
| user_favorite_questions | 0012 | **IV** |
| writing_outlines | phase C | **NI** |
| outline_nodes | phase C | **NI** |
| learning_plans | phase C | **NI** |
| learning_tasks | phase C | **NI** |
| ai_usage_logs | 0006 | **IV** (every LLM call logged: provider/model/prompt/tokens/latency/cost/status) |

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
| 2026-11-15 (Slice 7) | Evaluations + rewrites implemented + verified as POST-WRITING actions (ADR-016): 202 queued evaluations bound to immutable versions (composite FK same-essay), in-process background processing via app session factory (test-isolated), Task 1 / Task 2 / general LLM schemas with versioned prompts, half-band normalization + server-computed overall band, is_estimate always true, full usage logging incl. failures. Rewrites level_1–4 preserve meaning, results stored server-side; atomic accept applies only stored text with revision check, creates ai_rewrite version + accept_rewrite edit event, 409 on conflict/duplicate; Original never overwritten. Migration 0013 (essay_evaluations, essay_rewrites with source-matches-evaluation composite FK, edit-event rewrite_id + event enum extension; cascade delete keeps versions). Idempotency-Key on queue/rewrite/accept. Frontend: Evaluate dialog (snapshot→evaluate→poll, band/criteria/Chinese feedback, estimate badge, history/delete, rewrite preview + explicit accept). ADR-019. Verification: backend **302 passed** (19 new + 1 contract), Playwright **54 passed** (3 new), vitest 21, tsc/ESLint/build/ruff clean. Contract 66/88. |
| 2026-11-15 (Slice 6) | IELTS question bank implemented + verified: 60 original licensed-safe practice questions (18 Task 1 Academic across 6 chart types, 9 GT letters across 3 registers, 33 Task 2 across 5 question types; 18 topic tags; Chinese translations; text-based data so the bank is self-contained). Published+license gate in the repository layer; keyset pagination; task/topic/type filters; tags with counts; random; idempotent user-scoped favorites. essays.question_id FK attached with existence + task-type consistency validation and question_prompt autofill. Migration 0012 (4 tables + FK + idempotent uuid5 seed; offline --sql safe). E2E DB prep re-seeds after pytest truncation. Frontend: /ielts page (filters, favorites, random, detail with translation, start-writing → editor question section). ADR-018. Verification: backend **282 passed** (18 new + 1 contract), Playwright **51 passed** (4 new), vitest 21, tsc/ESLint/build/ruff clean. Contract 59/88 (header total corrected: the 3UX accept operation made it 88, previously miscounted as 87). |
| 2026-11-15 (Slice 5B) | Learning implemented + verified: deterministic SM-2 spaced repetition (unit-tested invariants), translation reviews with rule-first exact match + LLM semantic judging (any natural correct answer accepted), due prompts without answer leakage, progress/summary, weakness aggregation on issue detection, volume-adjusted weekly trends (errors per 1000 words), LLM practice generation. Migration 0011 (expression_progress with same-owner composite FK, expression_reviews, user_weaknesses). Frontend: /learning Center (review flow, summary, weaknesses). Verification: backend **262 passed** (17 new), Playwright **47 passed** (3 new), vitest 21, tsc/ESLint/build/ruff clean. Contract 53/87. |
| 2026-11-15 (Slice 5A) | Semantic RAG + extraction implemented + verified: embedding provider abstraction (mock + OpenAI-compatible), expression_embeddings VECTOR(1536) + HNSW cosine index (migration 0010), embeddings on create/update (rebuildable, best-effort), user-scoped semantic recall at query time, keyword/semantic/hybrid search, previously-learned recall upgraded to semantic-first, extraction from immutable versions with confirmation-before-save. Frontend: search-mode selector, History → Extract → confirmation dialog. Verification: backend **245 passed** (15 new), Playwright **44 passed** (2 new), vitest 21, tsc/ESLint/build/ruff clean. Contract 45/87. Semantic QUALITY requires a real embedding endpoint (mock vectors are pipeline-only). |
| 2026-11-15 (Slice 4) | Expression assistance + knowledge base implemented + verified: polish/translation with backend mode enforcement, persisted candidates, previously-learned keyword recall + LLM suitability labeling, atomic server-authoritative acceptance (essay_edit_events.expression_suggestion_id, migration 0009), knowledge base CRUD/search/archive with dedup + soft delete (migration 0008), /knowledge page, selection-driven inline assistance UI. Verification: backend **230 passed** (15 new), Playwright **42 passed** (4 new), vitest 21, tsc/ESLint/build/ruff clean. Contract operations 44/87. |
| 2026-11-15 (DeepSeek + finalized UX) | User decisions implemented (ADR-016/017): DeepSeek provider (OpenAI- + Anthropic-compatible, env-only credentials, mock strictly separated for tests, verify_llm.py + eval_ai.py harness with grammar/teaching datasets); finalized editor UX — separate question section (essays.question_prompt, migration 0007), hierarchical text outline (sections→paragraphs→sentences), automatic sentence-completion checking (abbreviations/decimals/quotes/IME/pause-safe, no manual button), hover floating feedback, click-blurred-to-reveal, Tab-to-accept via new atomic accept endpoint (contract 1.2.0), teaching icon, no Submit button during writing. Verification: backend 215+ passed, Playwright **38 passed**, vitest 21, tsc/ESLint/build/ruff clean. **Open item: rotated DeepSeek key must be placed in .env by the user (exposed chat credential NOT used); real AI quality evaluation pending that.** |
| 2026-11-15 (Slice 3) | Grammar core implemented + verified: LanguageTool 6.6 self-hosted (Docker; broken :latest/6.6 erikvl87 builds rejected, meyay image used), custom deterministic rules (Chinese punctuation, missing space), classification + Chinese short explanations, LLM deep-check only for uncertain fragments (capped), issue lifecycle (check/list/detail/validate/reveal/ignore/teaching), atomic self-correction with re-anchoring, contextual teaching with context-hash caching, LLM provider abstraction (mock + OpenAI-compatible) with versioned prompts and full usage logging. Migration 0006. Frontend: category-colored inline underlines, hint widgets with blurred answers, reveal/teach/ignore + Alt+R/T/I shortcuts, floating teaching card, independent-mode enforcement. Verification: backend **204 passed** (46 new), Playwright **37 passed** (7 new), vitest 12, tsc/ESLint/build/ruff clean. Environment: Docker data moved to D: (user-authorized; C: was full), LanguageTool container added. |
| 2026-11-15 (Slice 2D) | Writing sessions implemented + verified: two modes with server-derived enabled_features (backend enforcement), exam config + deadline, one-active-session rule, cancel, atomic submit (Final Snapshot, shared-original optimization, Edit Event, Idempotency-Key). Migration 0005 adds writing_sessions + essays UNIQUE(id,user_id) + composite same-owner FK. Frontend session controls: mode picker, exam countdown, submit/cancel. Verification: backend **158 passed** (14 new), Playwright **30 passed** (5 new), vitest 12, tsc/ESLint/build clean, ruff clean. Contract operations 26/87. |
| 2026-11-15 (Slice 2C) | TipTap writing editor live on /essays/[id]: debounced autosave + Ctrl+S + save status + conflict recovery (keep local / copy / load latest), word count, undo/redo, formatting toolbar, collapsible left outline (expanded by default), version history dialog with checkpoints + confirmed restore, IME-composition-safe saving. Unicode codepoint↔UTF-16↔ProseMirror mapping utilities with 12 unit tests. OpenAPI type generation pipeline (R11). Verification: Playwright **25 passed** (7 new editor tests), vitest 12 passed, tsc/ESLint/build clean. Fixed real defects: toolbar no-op on fresh unfocused editor; descendants() pruning in position mapping; E2E rate-limit exhaustion (E2E-only env relaxation). `awc-screenshots.mjs` review utility recreated. |
| 2026-11-15 (Slice 2B) | Working Document GET/PUT, snapshots, versions, restore implemented + verified: backend **144 passed** (50 new), ruff clean. Migration 0004 (essay_edit_events, essay_versions.label, idempotency_keys). Fixed two real defects found by tests: stale identity-map read under FOR UPDATE (populate_existing) and unreliable ON CONFLICT rowcount (RETURNING). ERD V1.2.1 increments recorded. Contract operations 21/87. |
| 2026-11-15 | Matrix created from full document review + live repository audit. Baseline re-verified: pytest 94 passed, ruff/tsc/ESLint/build clean, Playwright 18 passed. Slice 2A committed as `7baeb36`. Reconciliations R1–R12 recorded. |
