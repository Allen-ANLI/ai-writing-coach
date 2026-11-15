# Deployment Guide

**Status:** Slice 11b (2026-11-15). Production-style stack is defined and
config-complete; public deployment itself is user-gated (Directive §6).

## Topology

```
client → nginx (:80) → frontend (Next.js :3000)
                     → backend  (FastAPI :8000) → PostgreSQL 17 + pgvector
                                              → LanguageTool (internal)
                                              → LLM / embeddings (external, user-gated)
```

Only nginx is exposed. PostgreSQL, LanguageTool, backend and frontend stay on
the internal compose network. TLS terminates upstream of nginx (load balancer
or ingress); set `CORS_ORIGINS` and `FRONTEND_BASE_URL` to the public HTTPS
origin.

## Files

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Python 3.13-slim, non-root, migrations on start |
| `frontend/Dockerfile` | Node 22 multi-stage, `next start`, non-root |
| `backend/.dockerignore`, `frontend/.dockerignore` | Keep `.env*`, `node_modules`, `.next`, caches, tests out of images |
| `docker-compose.prod.yml` | Full stack; only nginx published |
| `infrastructure/nginx/nginx.conf` | Reverse proxy + security headers |
| `.env.production.example` | All required settings with CHANGE_ME markers |

`docker compose -f docker-compose.prod.yml config` validated 2026-11-15.
Image builds are verified by the CI `docker` job (build-only, no push, no
deployment): the dev machine cannot reach Docker Hub (`auth.docker.io`
times out), so local `docker build` is network-blocked here. The backend
image's runtime dependency closure is additionally guarded by
`tests/test_runtime_dependencies.py` (caught httpx being dev-only while
providers import it — fixed 2026-11-15). No public deployment happens
before authorization.

## Deploy

```bash
cp .env.production.example .env      # fill every CHANGE_ME; never commit
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps      # all healthy
curl http://localhost/api/v1/health               # {"data":{"status":"ok",...}}
```

## Scaling note (important)

The backend currently assumes a **single worker**: the rate limiter and the
evaluation/rewrite/outline background tasks are in-process. Before scaling to
multiple workers/replicas:

1. Move rate limiting to a shared store (the storage point is isolated in
   `app/core/rate_limit.py`).
2. Move background jobs to a durable queue (the queued-row protocol in
   `essay_evaluations`/`workflows` already supports a separate worker; see
   ADR-019/ADR-020).

## Health & observability

- `GET /api/v1/health` — liveness + real DB connectivity (200/503).
- Every response carries `X-Request-ID`; structured JSON access logs include
  request_id, method, path, status, duration_ms (`LOG_FORMAT=json`).
- AI calls are recorded in `ai_usage_logs` (provider/model/prompt/tokens/
  latency/cost/status) and surfaced at `/analytics/ai-usage*`.

## Rollback

Images are tagged per release; `docker compose ... up -d` with the previous
image tags rolls back the app. Migrations are additive and forward-only —
never edit an applied migration; restore data from backup if a migration must
be undone (see BACKUP_RECOVERY.md).
