# AGENTS.md — AI Writing Coach

This file defines repository-wide instructions for AI coding agents (including Codex).
Read it before changing code. More specific `AGENTS.md` files in subdirectories may add
constraints, but must not silently contradict this file.

## 0. Execution authority — Master Development Directive V2.0 (2026-11-15)

The user has commissioned autonomous completion of the **entire product** from the
current repository: all PRD functionality, frontend, backend, AI capabilities, database,
testing, monetization infrastructure and production readiness, verified before one final
public launch. No Private Alpha, Public Beta, early-access or partial commercial launch.
Internal development, local testing and automated verification are allowed.

- Do not stop at plans or milestone reports; continue implementation slice by slice
  (roadmap in `docs/DEVELOPMENT_PLAN.md` §3a; status in `docs/TRACEABILITY_MATRIX.md`).
- Full internal engineering authority: ERD/API/architecture changes, migrations,
  dependencies, refactors — with the obligations in §6/§7 (explain material changes,
  update docs + ADRs, keep contract aligned, add regression tests, preserve data).
- Human approval is required ONLY for: new material external costs; purchasing or
  activating paid services; irreversible destructive data operations; material legal,
  privacy or regulatory risks; public deployment and release.
- Ordinary Git commits on `main` are authorized (small, imperative, inspected diffs;
  §8). Never force-push, reset away work, or edit applied migrations in place.
- Never claim incomplete functionality is complete; distinguish implemented-and-verified
  / implemented-not-fully-verified / not-implemented in every report.
- The original design documents are authoritative starting references, not immutable
  restrictions; resolve contradictions explicitly in `docs/TRACEABILITY_MATRIX.md` §1.

## 1. Product and engineering context

AI Writing Coach is an English-writing training web application. Its core experience is
an inline-first writing editor: grammar feedback appears near the original text; users
can reveal corrections, request sentence-specific teaching, receive expression and
Chinese-to-English suggestions, and build a private expression knowledge base.

The approved engineering baseline is:

- Product requirements: PRD V1.1
- System design: System Design V1.1
- Database: Database ERD V1.2
- API contract: API Specification V1.1 (rev V1.1.1)
- Machine-readable contract: OpenAPI 3.1, version 1.1.1

All five baselines are present: PRD V1.1 (`docs/PRD_V1.1.docx`), System Design V1.1
(`docs/AI_Writing_Coach_System_Design_V1.1.md`), ERD V1.2, API Spec V1.1.1 and the
OpenAPI contract. Read the relevant sections before implementing a feature. If a
document is missing, do not invent its contents; report the missing dependency.

## 2. Technology stack

### Frontend
- Next.js (App Router)
- React
- TypeScript (strict mode)
- Tailwind CSS
- TipTap / ProseMirror for the writing editor
- TanStack Query for server state
- Zustand only for genuinely client-local shared state
- Playwright for end-to-end tests

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic
- Pytest
- HTTPX for API/client tests

### Data and infrastructure
- PostgreSQL with pgvector extension available
- Docker Compose for local infrastructure
- LanguageTool is a later application service, not required for the first
  repository bootstrap to be fully functional.
- Redis, Celery, Kubernetes, and distributed microservices are not part of
  the initial bootstrap. Add them only after a concrete requirement and an ADR.

### Contract
- OpenAPI 3.1 is the API contract.
- The checked-in OpenAPI file is the source of truth for frontend API type generation
  and backend contract verification.
- Do not independently invent frontend and backend request/response shapes.
- Pydantic schemas and TypeScript types must be checked against the OpenAPI contract.

## 3. Architecture rules

- Use a modular monolith. Do not split the backend into microservices.
- Frontend and backend live in one repository (Monorepo), but remain separate apps.
- Frontend communicates with the backend through the documented HTTP API.
- Frontend must never call LLM providers directly.
- Provider credentials and prompts stay on the server.
- Keep domain logic out of route handlers and React components.
- Use dependency injection for database sessions, authentication, and external clients.
- Use explicit service/repository boundaries where they improve clarity; do not create
  unnecessary abstraction layers for trivial CRUD.
- Do not add LangChain or LangGraph to the bootstrap. Introduce LangGraph only for
  workflows that require durable multi-step state or human confirmation.
- Rule-first grammar checking: run deterministic rules first; invoke an LLM only when
  the product rule requires it or the user explicitly requests deeper teaching.
- Detailed teaching is contextual to the user's current sentence and relevant paragraph.
  Do not build a reusable generic teaching-content library.

## 4. Non-negotiable domain invariants

### Essays and snapshots
1. Each Essay has exactly one current `EssayWorkingDocument`.
2. Autosave updates the Working Document and increments `server_revision`.
3. Autosave does not create an `EssayVersion`.
4. `EssayVersion` records are immutable snapshots.
5. `version_no` is separate from `server_revision`.
6. Never overwrite or mutate the Original Snapshot.
7. Restoring a snapshot copies its content into the Working Document; it does not
   modify the source snapshot.
8. Evaluation always targets an immutable `version_id`, never a live Working Document.

### Live grammar issues
1. A live `WritingIssue` is anchored to `source_server_revision`.
2. `essay_version_id` may be null until an exact-source-revision snapshot is created.
3. A snapshot may archive only Issues whose `source_server_revision` exactly matches
   the snapshot's `source_revision`.
4. Never apply old text offsets to a newer revision without reliable position mapping.
5. API offsets use `unicode_codepoint`; the frontend must explicitly convert to and from
   ProseMirror positions. Do not mix Unicode code points, JavaScript UTF-16 indices,
   and ProseMirror positions.

### Atomic editing operations
1. User correction validation must atomically coordinate:
   - Working Document update,
   - Issue status update,
   - resolved revision metadata,
   - EssayEditEvent creation.
2. Any LLM judgement needed for validation must happen outside a long-running DB
   transaction. Re-check `base_revision` inside the short transaction before writing.
3. If the revision changed, return a conflict; never partially commit the operation.
4. Accepting an expression suggestion must validate ownership and revision, apply the
   submitted replacement document, increment the revision, update suggestion state,
   and create an Edit Event atomically.
5. Accepting an AI rewrite must use the completed server-side rewrite result, not
   arbitrary client-supplied replacement text. In one transaction, update the Working
   Document, create an `ai_rewrite` snapshot, set `result_version_id`, and create an
   Edit Event.

### Editor UX (revised 2026-11-15, ADR-024 — supersedes ADR-016 §2.3–2.6)
1. The essay question is shown in a separate non-editable section
   (`essays.question_prompt`); never mixed into the editable document.
2. The left panel is a **conversational planner chat** with the agent: agree on
   the outline before writing, revise it mid-writing. No Plan button, no
   document-outline tree in the editor. Confirmed outlines drive inline hints.
3. Grammar checking is automatic on sentence completion (debounce +
   cancellation); no manual check button, no numbered errors. Incomplete
   input is never checked prematurely. The checked sentence is the completed
   sentence at/before the cursor; findings merge per range so multi-sentence
   underlines coexist (ADR-025). Rule-first still applies, plus a
   whole-sentence LLM scan for errors rules miss (offsets validated, quota
   metered). Opening the editor auto-creates an assisted session (unless the
   user explicitly cancelled one), so feedback works without manual setup.
4. Hovering an underlined error floats a card (slightly transparent surface)
   that shows the short explanation, the **correction directly (no blur, no
   reveal click)**, alternatives, and the contextual detailed explanation
   (LLM, cached) with loading/error/retry states. It must not obstruct editing.
5. Tab replaces the original while the hover card is visible with a
   suggestion; otherwise Tab is normal. Acceptance applies the server-stored
   suggestion atomically. Esc closes; Alt+I ignores. Clicking an error only
   places the caret — no click-to-teach.
6. Gray **Chinese** inline ghost hints guide sentence-by-sentence through the
   flattened confirmed outline (ADR-025): the current idea persists at the
   caret while the sentence is unfinished; on completion the planner/progress
   endpoint judges fulfillment — fulfilled advances to the next idea, otherwise
   the hint stays. The on/off switch lives in the planner panel
   (preferences.ghost_hints_enabled). Guidance only: never persisted, never
   counted, never auto-inserted into the essay.
7. No Submit Essay button during writing; evaluation/assessment/rewrites are
   post-writing actions. The session submit API remains for that flow.
8. The UI language is Simplified Chinese (mainland-China users); essay content,
   question prompts and IELTS question text stay English.

### Authentication
1. `auth_sessions` represents a stable device login session.
2. `auth_refresh_tokens` represents individual Refresh Token rotation records.
3. Refresh rotation does not create a new device Session.
4. Store only a secure hash of Refresh Tokens, never plaintext.
5. Consume the old token and create its replacement atomically.
6. Detect reuse of a consumed token and revoke the associated token family/session
   according to the authentication design.
7. Access tokens are short-lived JWTs. Refresh tokens are opaque HttpOnly Secure cookies.
8. Protect cookie-authenticated endpoints against CSRF and handle concurrent refresh
   requests with a single-flight strategy on the client.

### AI and user data
1. A user's private essays, expressions, embeddings, reviews, evaluations, and workflows
   must be scoped to the authenticated user.
2. Never trust a client-supplied `user_id` for authorization.
3. Initial grammar responses must not leak unrevealed correction text in hidden fields,
   HTML, logs, or other browser-readable payloads.
4. Validate model output with Pydantic and validate text ranges against the source text.
5. Never let an LLM decide authorization or execute arbitrary database writes.
6. Log provider, model, prompt version, token usage, latency, cost estimate, and status
   where available. Avoid logging full essay text unless explicitly required and approved.

## 5. Repository layout

Target layout:

```text
ai-writing-coach/
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── stores/
│   │   └── types/
│   ├── public/
│   ├── package.json
│   └── ...
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── infrastructure/
│   │   ├── modules/
│   │   ├── ai/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── ...
├── contracts/
│   ├── openapi.yaml
│   └── generated/
├── docs/
│   ├── PRD.md
│   ├── SYSTEM_DESIGN.md
│   ├── DATABASE_ERD.md
│   ├── API_SPECIFICATION.md
│   ├── DEVELOPMENT_PLAN.md
│   ├── ADR/
│   └── templates/
├── infrastructure/
│   ├── docker/
│   └── postgres/
└── scripts/
```

Do not create empty directories merely to match the tree. Add a directory when the
first real file in that area is introduced.

## 6. Coding standards

### General
- Prefer small, reviewable changes.
- Do not rewrite unrelated files.
- Do not silently change product behavior or approved API contracts.
- Do not add dependencies without explaining why they are needed.
- Avoid speculative abstractions and premature optimization.
- Use clear names and type annotations.
- Keep secrets out of source control.
- Update documentation when a behavior or contract changes.

### TypeScript / React
- Keep TypeScript strict mode enabled.
- Avoid `any`; if unavoidable, isolate it and explain why.
- Keep server state in TanStack Query; use Zustand only for client-local state.
- Keep editor-specific logic inside the editor feature/extensions.
- Do not store derived state when it can be computed.
- Ensure editor decorations/widgets are not part of the persisted essay body or word count.
- Add accessible labels and keyboard behavior for interactive controls.

### Python / FastAPI
- Use type hints and Pydantic request/response models.
- Keep routers thin; place business logic in services.
- Use SQLAlchemy 2.x typed mappings.
- Use explicit transaction boundaries.
- Do not perform network calls to LLM/LanguageTool while holding long DB transactions.
- Use Alembic for every schema change; never rely on manual production DB edits.
- Use dependency injection for DB sessions and authenticated users.
- Return the documented error envelope and stable error codes.

### Database
- PostgreSQL is the source of truth.
- Use UUID primary keys.
- Use `TIMESTAMPTZ` for timestamps and `NUMERIC` for money/scores.
- Use JSONB for document snapshots and genuinely flexible structured payloads, not
  to hide core relational data.
- Use `VARCHAR + CHECK` for evolving status fields initially.
- Add indexes based on query patterns, not indiscriminately.
- Use composite constraints/foreign keys where needed to enforce same-Essay and
  same-user ownership invariants.
- Every migration must be reversible where practical and reviewed for data safety.

## 7. Testing requirements

For every task:
1. Add or update relevant tests.
2. Run the narrowest relevant test suite.
3. Run formatting/lint/type checks available in the project.
4. Report commands run and exact outcomes.
5. Do not claim tests passed if they were not run.

Minimum expected checks as the project grows:
- Backend: `pytest`
- Frontend: lint, TypeScript check, unit tests where configured
- E2E: Playwright for user-visible critical flows
- Contract: OpenAPI validation and generated-type consistency
- Database: PostgreSQL integration tests for transactions, foreign keys, ownership,
  revision conflicts, and snapshot immutability.

## 8. Git workflow

- Keep `main` releasable.
- Use short-lived feature branches for non-trivial work, e.g. `feature/bootstrap-monorepo`.
- Make small commits with imperative messages, e.g. `chore: bootstrap monorepo`.
- Never force-push or rewrite shared history unless explicitly requested.
- Do not commit `.env`, API keys, credentials, local databases, build outputs, or
  personal data.
- Before committing, inspect `git status` and the diff.

## 9. How to execute a task

Before editing:
1. Read this file and relevant design/API documents.
2. Inspect the existing repository; do not assume it is empty.
3. Identify affected modules and dependencies.
4. State a concise implementation plan.
5. Flag any conflict with ERD/API/product invariants before changing the contract.

During implementation:
1. Implement only the requested task scope.
2. Prefer a thin vertical slice over broad unfinished scaffolding.
3. Keep API contract and code aligned.
4. Add tests with the implementation.
5. Do not stub a feature as "complete" if its core behavior is not implemented.

After implementation, report:
- Files created/modified.
- Design decisions and dependencies added.
- Commands executed.
- Test/lint/type-check results.
- Known limitations and follow-up tasks.
- Any design decision that needs human approval.

## 10. Bootstrap task scope (historical — completed)

The original bootstrap task (Stage 0/1) is complete: Monorepo, Next.js frontend,
FastAPI backend with health endpoint, Docker Compose PostgreSQL + pgvector, environment
examples, smoke tests. Authentication (Slice 1/1.5) and Essay CRUD (Slice 2A) are also
complete and committed. Current work follows the Directive V2.0 slice roadmap in
`docs/DEVELOPMENT_PLAN.md` §3a under the execution authority in §0.
