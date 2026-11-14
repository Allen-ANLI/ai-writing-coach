# AI Writing Coach — Preflight Report & Implementation Plan

**Task:** `CODEX_FIRST_IMPLEMENTATION_TASK.md` — Step 1 (Preflight only)
**Baseline:** AGENTS.md / MONOREPO_INITIALIZATION_TASKS.md V1.0
**Status:** Preflight complete. **No project files created, modified, moved or deleted.**
**Blocking:** Decisions A–D pending; Docker daemon not running. Implementation not started.

---

## 1. Preflight Report

### 1.1 Repository and Git state

| Check | Result |
|---|---|
| Current working directory | `D:\DOCUMENTS\Projects` |
| Repository root | **None.** `git rev-parse --show-toplevel` -> `fatal: not a git repository` |
| Current branch | **None** (Git not initialized) |
| `git status --short --branch` | **Executed, failed:** `fatal: not a git repository (or any of the parent directories): .git` |
| Git executable | Available — `git version 2.45.1.windows.1` |

> Warning: `D:\DOCUMENTS\Projects` is a general projects container directory, not a
> dedicated project repository. Running `git init` here would place all future unrelated
> projects under one repository. Repository root location requires confirmation
> (Decision A).

### 1.2 Existing files (all preserved, zero modifications)

| File / Directory | Size | Notes |
|---|---|---|
| `AGENTS.md` | 12,787 B | Read. Repository-wide agent rules |
| `MONOREPO_INITIALIZATION_TASKS.md` | 8,695 B | Read. V1.0 bootstrap task list |
| `CODEX_FIRST_IMPLEMENTATION_TASK.md` | 1,565 B | Current task instruction |
| `DATABASE_ERD_V1.2.md` | 22,351 B | ERD V1.2, 29 entities, Final Development Baseline |
| `API_SPECIFICATION_V1.1.md` | 20,664 B | API Spec V1.1, Final Development Baseline |
| `OPENAPI_V1.1.yaml` | 68,863 B | `openapi: 3.1.0`, `info.version: 1.1.0` |
| `AI Writing Coach RPD.docx` | 63,996 B | Actual content is **PRD V1.1** (1084 paragraphs, Chinese). Filename "RPD" is a typo |
| `IELTS Writing Coach/` | — | **Empty directory** (recursive listing returned nothing) |

Additional findings:

- **No lockfiles present.** `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`,
  `poetry.lock`, `uv.lock` all absent. No package manager has been chosen yet.
- **No** `frontend/`, `backend/`, `docs/`, `contracts/`, `infrastructure/`, `scripts/`.
- During preflight a temporary helper script `_preflight_docx.py` was created to read the
  `.docx` and **was deleted afterwards**. No other file was touched.

### 1.3 Runtimes and toolchain

| Tool | Status | Version / Location |
|---|---|---|
| Node.js | **Not installed** | Not on PATH. No nodejs/nvm/fnm/volta under `C:\Program Files`, `C:\Program Files (x86)`, `%LOCALAPPDATA%\Programs`, `%APPDATA%`, `D:\Software` |
| npm / pnpm / yarn | **Not installed** | All three: `CommandNotFoundException` |
| `python` | Available | **3.13.9** — `D:\Software\Anaconda3\python.exe` |
| `py` default | Available | **3.14** — `C:\Users\12458\AppData\Local\Python\pythoncore-3.14-64\python.exe` |
| pip | Available | 25.3 (Anaconda base) |
| uv | Not installed | — |
| Docker CLI | Available | 29.9.2 |
| Docker Compose | Available | v5.6.1 |
| Docker daemon | **Not running** | `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` |
| Docker Desktop | Installed | `C:\Program Files\Docker\Docker\Docker Desktop.exe` (Test-Path = True) |
| winget | Available | v1.29.380. Source lists `OpenJS.NodeJS` 26.12.1, 22.23.5, etc. |
| Network | Reachable | PyPI 200, registry.npmjs.org 200, nodejs.org 200 |

Python packages already in Anaconda base:

    SQLAlchemy 2.0.43
    pydantic 2.12.4
    pydantic-settings 2.12.0
    httpx 0.28.1
    pytest 8.4.2
    ruff 0.12.0

Missing for the bootstrap: `fastapi`, `uvicorn`, `alembic`, `psycopg`,
`openapi-spec-validator`.

### 1.4 Approved contract files

| Required path | Present | Actual source |
|---|---|---|
| `docs/DATABASE_ERD.md` | No | Source exists at root: `DATABASE_ERD_V1.2.md` |
| `docs/API_SPECIFICATION.md` | No | Source exists at root: `API_SPECIFICATION_V1.1.md` |
| `contracts/openapi.yaml` | No | Source exists at root: `OPENAPI_V1.1.yaml` |
| `docs/SYSTEM_DESIGN.md` | No | **Approved document MISSING.** No System Design V1.1 anywhere in workspace |
| `docs/PRD.md` | No | Only `.docx` (PRD V1.1). No Markdown version |

Per AGENTS.md, the missing System Design V1.1 will be **recorded as a missing dependency**.
Its contents will not be invented or substituted.

### 1.5 Conflicts with the planned structure

1. **No Git repository** — cannot create `feature/bootstrap-monorepo` as required by
   task section 1.
2. **Seven documents already at root** overlap the target `docs/` and `contracts/`
   layout. Copying them creates a **duplicate OpenAPI source of truth**, exactly the risk
   task section 2 warns against. Root originals must be handled explicitly (Decision B).
3. **`/api/v1/health` is absent from the OpenAPI contract.** A full-text search for
   `health` in `OPENAPI_V1.1.yaml` returned no match. The task requires this endpoint,
   but AGENTS.md forbids silently changing an approved contract (Decision C).
4. **The OpenAPI file uses YAML anchors/aliases** (e.g. `WorkingDocumentUpdate: *id002`,
   a PyYAML dump artifact). Validation handles this correctly, but future type generation
   must resolve aliases first. Recorded as a follow-up item.
5. **Empty `IELTS Writing Coach/` directory** does not match the product name and may be
   an early placeholder. Left untouched unless nominated as the repository root.
6. **Port availability (3000 / 8000 / 5432) not yet checked.** Will be verified before
   starting services.

---

## 2. Decisions requiring your approval

| # | Topic | Options | Recommendation |
|---|---|---|---|
| **A** | Repository root | (1) In place at `D:\DOCUMENTS\Projects`; (2) use the empty `IELTS Writing Coach/`; (3) create `ai-writing-coach\` and relocate documents | **(3)** — matches the AGENTS.md target tree and avoids polluting the projects container. Relocation means *moving* files and needs explicit approval |
| **B** | Root document originals | (1) Copy into `docs/` + `contracts/`, keep originals (duplicate-source risk); (2) move to target paths; (3) copy, then move originals into `docs/_inbox/` and declare the single source of truth in README | **(2)** move — eliminates duplication. If you require "never move", fall back to **(3)** |
| **C** | Health endpoint vs contract | (1) Add `/health` to the contract (additive, operational, no business-semantics change); (2) leave contract untouched and document health as an out-of-contract ops endpoint | **(1)**, but **requires your approval of a contract change**. Until approved, implement **(2)** and document the deviation |
| **D** | Installing Node.js | (1) winget machine-wide install (may need admin — disallowed by rules); (2) **portable zip** extracted to a user/project `.tools\` directory (no admin) | **(2)** Node **22 LTS (22.23.5)** portable + bundled npm. **Requires your approval to install software** |
| **E** | Starting Docker Desktop | Daemon must be started (usually no admin, but may show licence/WSL prompts) | I will attempt to start it; if interaction is needed, **please start it manually**. Otherwise all DB-related acceptance checks cannot run |
| **F** | Python environment | (1) venv from Anaconda 3.13; (2) venv from py 3.14 | **(1)** `backend\.venv` on 3.13 — binary wheels are complete; 3.14 is higher risk. Dependencies install into the venv only, never into Anaconda base |
| **G** | Missing documents | System Design V1.1 missing; PRD only as `.docx` | Record System Design as **missing**. Keep the PRD `.docx`; `docs/PRD.md` will state "docx only". `DEVELOPMENT_PLAN.md` will contain only the explicitly agreed Stage 0/1, with later stages marked **TBC** — nothing invented |

**Current blockers:** A/B/C/D undecided, plus Docker daemon down. No files will be
written until these are resolved.

---

## 3. Implementation plan (to execute after approval)

### Stage 0 — Documents and contract

- Place ERD V1.2 at `docs/DATABASE_ERD.md`.
- Place API Spec V1.1 at `docs/API_SPECIFICATION.md`.
- Place OpenAPI 1.1.0 at `contracts/openapi.yaml` — the single source of truth.
- Preserve the PRD `.docx`; add `docs/PRD.md` noting the docx-only baseline.
- Add `docs/SYSTEM_DESIGN_MISSING.md` recording the missing approved dependency.
- Add `docs/DEVELOPMENT_PLAN.md` (Stage 0/1 agreed scope; later stages TBC).
- Add `docs/README.md` declaring document authority and precedence.
- Ensure exactly one OpenAPI file is referenced by tooling.

### Stage 1a — Repository root

- `git init` at the approved root; create branch `feature/bootstrap-monorepo`.
- Add `README.md`, `.gitignore`, `.env.example`, `docker-compose.yml`.
- Keep the existing `AGENTS.md`.
- Create `infrastructure/` and `scripts/` only when their first real file appears.
- No nested Git repositories inside `frontend/` or `backend/`.

### Stage 1b — Backend (FastAPI)

- `backend/pyproject.toml`, venv on Python 3.13.
- Dependencies: fastapi, uvicorn, pydantic, pydantic-settings, SQLAlchemy 2.x,
  alembic, psycopg[binary], plus dev: pytest, httpx, ruff, openapi-spec-validator.
- Structure: `app/main.py`, `app/api/`, `app/core/` (settings, response envelope),
  `app/infrastructure/` (engine/session).
- `GET /api/v1/health` performs a real `SELECT 1` against PostgreSQL.
- Success envelope (database reachable):

        {"data": {"status": "ok", "database": "connected"}, "meta": {"request_id": "..."}}

- Database unreachable: HTTP 503 with the stable error envelope; never falsely report
  `connected`.

        {"error": {"code": "DATABASE_UNAVAILABLE", "message": "..."}, "meta": {"request_id": "..."}}

- SQLAlchemy 2.x + Alembic configured, **no domain models yet**.
- CORS restricted to the local frontend origin only.
- Pytest + HTTPX smoke tests covering both healthy and unavailable paths.
- `backend/README.md` with setup, run, migration and test commands.

### Stage 1c — Frontend (Next.js)

- Next.js App Router + TypeScript **strict mode** + Tailwind CSS + ESLint.
- Typed API base URL from `NEXT_PUBLIC_API_BASE_URL` (default
  `http://localhost:8000/api/v1`).
- Minimal landing/health page with a client-side health check against FastAPI.
- Placeholder feature folders only; no product features.
- `frontend/README.md` with install, dev, lint, build commands.

### Stage 1d — PostgreSQL + pgvector

- Compose service `db` using a pgvector-enabled image (e.g. `pgvector/pgvector:pg16`).
- DB name / user / password / port from environment variables.
- Persistent named volume; `pg_isready` healthcheck.
- `infrastructure/postgres/init.sql` running `CREATE EXTENSION IF NOT EXISTS vector;`.
- `.env.example` committed; `.env` never committed.
- Document start / stop / logs / reset commands.
- No Redis, Celery, Kubernetes or LanguageTool.

---

## 4. Verification plan (Step 3)

Every command below will be run and its exact outcome reported. No check will be
reported as passing unless it was actually executed.

| Check | Command (from repository root) |
|---|---|
| Backend tests | `backend\.venv\Scripts\python -m pytest backend/tests -q` |
| Backend lint/format | `backend\.venv\Scripts\python -m ruff check backend` |
| Frontend lint | `npm run lint` (in `frontend/`) |
| TypeScript check | `npx tsc --noEmit` (in `frontend/`) |
| Production build | `npm run build` (in `frontend/`) |
| OpenAPI 3.1 validation | `backend\.venv\Scripts\python -m openapi_spec_validator contracts/openapi.yaml` |
| Database health | `docker compose up -d db` then `docker compose exec db pg_isready -U <user>` |
| pgvector extension | `docker compose exec db psql -U <user> -d <db> -c "CREATE EXTENSION IF NOT EXISTS vector;"` |
| Backend health (live) | `Invoke-RestMethod http://localhost:8000/api/v1/health` |
| Browser -> backend | Load `http://localhost:3000`, confirm the health page renders backend status |
| Whitespace / diff hygiene | `git diff --check` |

Checks that depend on Node.js (Decision D) or the Docker daemon (Decision E) will be
reported as **blocked / not run** if those prerequisites remain unresolved.

---

## 5. Explicitly out of scope

Authentication (JWT / register / login / refresh), all 29 ERD models, full domain
migrations, TipTap editor and extensions, Essay CRUD and autosave, LanguageTool,
grammar issue lifecycle, LLM providers and prompts, evaluation and rewrite, embeddings /
pgvector retrieval / RAG, LangGraph, Redis, Celery, Kubernetes, billing, production
deployment.

---

## 6. Awaiting your reply

Please confirm:

1. **A** — repository root location.
2. **B** — how to handle the seven root documents (move vs copy).
3. **C** — whether `/health` may be added to `contracts/openapi.yaml`.
4. **D** — approval to install portable Node.js 22 LTS.
5. **E** — whether you will start Docker Desktop, or want me to attempt it.

Decisions F and G will follow the recommendations above unless you object.
No commits will be made unless you explicitly request them.