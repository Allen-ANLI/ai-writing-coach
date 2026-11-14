# Codex — First Implementation Task

Read `AGENTS.md` and `docs/MONOREPO_INITIALIZATION_TASKS.md`.

## Step 1: Preflight only

Before editing anything:
1. Confirm repository root and current Git branch.
2. Run `git status --short --branch`.
3. Inspect existing files and package-manager lockfiles.
4. Check installed Node.js, package manager, Python, Docker and Docker Compose.
5. Identify existing files that would conflict with the planned structure.
6. Confirm whether the three approved contract files are present:
   - `docs/DATABASE_ERD.md`
   - `docs/API_SPECIFICATION.md`
   - `contracts/openapi.yaml`

Return a concise preflight report and implementation plan. Do not overwrite or delete existing files.

## Step 2: Implement bootstrap

After the preflight report, proceed with the Stage 1 bootstrap described in
`docs/MONOREPO_INITIALIZATION_TASKS.md`:
- Next.js App Router + TypeScript strict mode frontend.
- FastAPI backend with `/api/v1/health`.
- PostgreSQL + pgvector via Docker Compose.
- Environment examples and CORS for local development.
- Minimal backend smoke test and frontend health check.
- README instructions.

Do not implement authentication, Essay CRUD, TipTap, LanguageTool, LLM, RAG,
LangGraph, Redis, Celery, Kubernetes or billing.

## Step 3: Verify

Run and report:
- backend tests;
- frontend lint;
- TypeScript check;
- frontend production build;
- OpenAPI 3.1 validation;
- Docker/PostgreSQL health;
- browser-to-backend health request.

Do not claim a check passed unless you ran it. Do not commit changes unless requested.
