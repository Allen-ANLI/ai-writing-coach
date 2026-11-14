# AI Writing Coach — Monorepo Initialization Task List

**Plan version:** V1.0  
**Status:** Ready for Codex execution  
**Scope:** Stage 0 close-out + Stage 1 repository bootstrap  
**Architecture:** Monorepo / Modular Monolith

---

## 0. Objective

Create a reproducible local development repository in which:

- Next.js frontend starts successfully.
- FastAPI backend starts successfully.
- PostgreSQL with pgvector starts through Docker Compose.
- Frontend can call the backend health endpoint.
- Backend can connect to PostgreSQL and report database health.
- Backend and frontend smoke tests pass.
- OpenAPI contract and design documents are checked into the repository.

This task does **not** implement product features such as authentication, essay CRUD,
TipTap editor behavior, grammar checking, LLM calls, RAG, or LangGraph.

## 1. Preflight: inspect and protect the workspace

- [ ] Confirm the current working directory and repository root.
- [ ] Run `git status --short --branch`.
- [ ] Inspect existing files and package managers before creating anything.
- [ ] Do not overwrite existing project files without reporting the conflict.
- [ ] Confirm Node.js, package manager, Python, Docker and Docker Compose versions.
- [ ] Confirm whether the repository is already initialized with Git.
- [ ] Create a feature branch `feature/bootstrap-monorepo` if Git is initialized and the branch is available.

**Acceptance:** Existing work is preserved; environment and repository state are reported.

## 2. Stage 0 contract/document setup

- [ ] Place `DATABASE_ERD_V1.2.md` in `docs/DATABASE_ERD.md`.
- [ ] Place `API_SPECIFICATION_V1.1.md` in `docs/API_SPECIFICATION.md`.
- [ ] Place the approved System Design and PRD in `docs/` if available.
- [ ] Place `OPENAPI_V1.1.yaml` in `contracts/openapi.yaml`.
- [ ] Add a `docs/DEVELOPMENT_PLAN.md` containing the agreed phase plan.
- [ ] Add a short `docs/README.md` explaining which document is authoritative.
- [ ] Ensure no duplicate stale OpenAPI file is accidentally used by code generation.

**Acceptance:** Repository contains one clearly designated OpenAPI source of truth and
the exact approved design baselines. If a source document is unavailable, record it as
missing instead of fabricating or substituting it.

## 3. Monorepo root

Create or verify:

- [ ] `AGENTS.md`
- [ ] `README.md`
- [ ] `.gitignore`
- [ ] `.env.example`
- [ ] `docker-compose.yml`
- [ ] `frontend/`
- [ ] `backend/`
- [ ] `contracts/`
- [ ] `docs/`
- [ ] `infrastructure/`
- [ ] `scripts/`

Use one repository. Do not introduce a second Git repository inside `frontend/` or
`backend/`.

**Acceptance:** Root layout is clear, no nested Git repositories, no secrets committed.

## 4. Frontend bootstrap

- [ ] Initialize Next.js App Router with TypeScript strict mode.
- [ ] Configure Tailwind CSS and ESLint.
- [ ] Create a minimal landing/health page.
- [ ] Add a typed API base URL configuration using environment variables.
- [ ] Add a minimal client-side health check calling FastAPI.
- [ ] Add a placeholder feature folder structure without implementing product features.
- [ ] Add a frontend README with install, dev, lint and build commands.

Suggested initial environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

**Acceptance:**
- `npm run dev` (or the chosen package-manager equivalent) starts.
- Frontend builds successfully.
- TypeScript strict check passes.
- Health page can display backend status when backend is running.

## 5. Backend bootstrap

- [ ] Initialize Python project using `pyproject.toml`.
- [ ] Initialize FastAPI application.
- [ ] Add `/api/v1/health` endpoint.
- [ ] Health endpoint checks PostgreSQL connectivity.
- [ ] Define a minimal consistent response envelope.
- [ ] Add configuration via environment variables.
- [ ] Add SQLAlchemy 2.x and Alembic configuration, but do not create all domain models yet.
- [ ] Add Pytest and HTTPX smoke test.
- [ ] Add backend README with setup, run, migration and test commands.

Health response when database is available:

```json
{
  "data": {
    "status": "ok",
    "database": "connected"
  }
}
```

If the database is unavailable, return a service-unavailable response with a stable
error envelope; do not report `"connected"` falsely.

**Acceptance:**
- FastAPI starts locally.
- `/api/v1/health` returns healthy only when database is reachable.
- Pytest smoke test passes.
- Application imports without requiring production secrets.

## 6. PostgreSQL + pgvector

- [ ] Add PostgreSQL image/version with pgvector support to Docker Compose.
- [ ] Configure database name, user, password and port via environment variables.
- [ ] Add persistent named volume.
- [ ] Add healthcheck using `pg_isready`.
- [ ] Enable `vector` extension in a documented initialization script or migration.
- [ ] Add `.env.example`; do not commit `.env`.
- [ ] Document start, stop, logs and reset commands.

**Acceptance:**
- `docker compose up -d db` starts the database.
- `pg_isready` succeeds.
- `CREATE EXTENSION vector;` succeeds.
- Data persists across container restart.

Do not add Redis, Celery, Kubernetes or LanguageTool to the initial compose file unless
the current bootstrap has a concrete tested need.

## 7. Local integration

- [ ] Configure frontend API URL.
- [ ] Configure backend database URL.
- [ ] Add CORS for the local frontend origin only.
- [ ] Start database, backend and frontend.
- [ ] Verify frontend calls backend health endpoint.
- [ ] Verify backend health reflects actual PostgreSQL connectivity.
- [ ] Add a single documented command sequence for a clean local start.

**Acceptance:** Browser → Next.js → FastAPI → PostgreSQL health path works locally.

## 8. Quality gates

- [ ] Backend formatting/lint command configured.
- [ ] Backend `pytest` passes.
- [ ] Frontend lint passes.
- [ ] Frontend TypeScript check passes.
- [ ] Frontend production build passes.
- [ ] OpenAPI YAML parses and validates as OpenAPI 3.1.
- [ ] No secrets or local database files are tracked.
- [ ] `git diff --check` passes.
- [ ] README setup instructions work from a clean checkout.

**Acceptance:** All commands and outcomes are recorded in the Codex completion report.

## 9. Git and handoff

- [ ] Review `git status` and full diff.
- [ ] Ensure no unrelated files changed.
- [ ] Summarize created files and decisions.
- [ ] List tests and exact outcomes.
- [ ] List known gaps.
- [ ] Commit only if explicitly requested by the user; otherwise leave changes ready for review.

**Acceptance:** A reproducible bootstrap is ready for human review.

---

## 10. Explicitly out of scope

Do not implement these in the bootstrap task:

- JWT registration/login/refresh flows.
- SQLAlchemy models for all 29 ERD entities.
- Full Alembic domain migration.
- TipTap editor and custom extensions.
- Essay CRUD and autosave.
- LanguageTool integration.
- Grammar Issue lifecycle.
- LLM provider abstraction or prompts.
- Essay evaluation or rewrite.
- Embeddings, pgvector retrieval or RAG.
- LangGraph workflows.
- Payments, subscription plans or production deployment.

These are subsequent vertical slices. Keep the bootstrap small and verifiable.

## 11. Codex execution prompt

Paste this into Codex after opening the intended repository:

> Read `AGENTS.md` and `docs/DEVELOPMENT_PLAN.md` first. Execute the Monorepo bootstrap task in `docs/MONOREPO_INITIALIZATION_TASKS.md`.
>
> Begin by inspecting the current workspace, Git status, installed runtimes and existing files. Do not assume the repository is empty and do not overwrite existing work. First return a concise preflight report and implementation plan. Then implement the bootstrap scope only: Next.js TypeScript frontend, FastAPI backend with a database-aware `/api/v1/health` endpoint, PostgreSQL + pgvector Docker Compose, environment examples, documentation and smoke tests.
>
> Do not implement authentication, Essay CRUD, TipTap, grammar checking, LLM, RAG, LangGraph, Redis, Celery or Kubernetes. Keep the checked-in `contracts/openapi.yaml` as the API contract; do not silently alter its business semantics. Run all relevant tests, lint, type checks and build commands. Report exact files, commands, results and remaining issues. Do not commit unless I explicitly ask.

## 12. Completion definition

The bootstrap is complete only when:

1. A clean checkout can follow README instructions.
2. PostgreSQL + pgvector is healthy.
3. FastAPI reports real database connectivity.
4. Next.js can call the FastAPI health endpoint.
5. Backend tests, frontend lint/type/build checks pass.
6. OpenAPI contract validates.
7. No domain feature has been falsely marked complete.
