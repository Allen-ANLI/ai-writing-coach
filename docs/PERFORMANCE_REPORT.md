# Performance Report

**Date:** 2026-11-15 (Slice 11b; re-verified same day after the general rate
limiter landed)
**Method:** `scripts/perf_probe.py` against an isolated dev backend (FastAPI +
PostgreSQL 17 + pgvector, single worker, Windows dev machine). 30 samples per
endpoint, throwaway user, non-AI paths only. The probe backend runs with
`API_RATE_LIMIT_MAX_REQUESTS=0` (the default 300/min per-IP limiter otherwise
trips during the probe — observed and confirmed working). Raw data:
`test-results/perf/report.json`.

## Results (milliseconds)

| Endpoint | P50 | P95 | Max |
|---|---|---|---|
| GET /essays | 12.8 | 34.1 | 37.4 |
| GET /essays/{id} | 13.7 | 35.9 | 39.6 |
| GET working-document | 14.7 | 35.5 | 39.1 |
| PUT working-document (autosave) | 24.4 | 46.4 | 49.6 |
| POST snapshot | 29.0 | 54.1 | 83.3 |
| GET versions | 17.4 | 43.7 | 55.6 |
| GET /ielts/questions | 19.2 | 60.1 | 64.0 |
| GET /ielts/tags | 15.4 | 34.5 | 35.1 |
| GET /billing/plans | 13.3 | 37.9 | 38.1 |
| GET /learning/summary | 17.6 | 40.7 | 41.2 |
| GET /users/me | 13.3 | 33.8 | 35.1 |

**Worst P95 = 60.1 ms — target P95 < 500 ms: PASS** (≈8× headroom).
Earlier 20-sample run: worst P95 55.0 ms — consistent.

## Notes
- AI endpoints are excluded (latency dominated by the external provider;
  tracked per-call in `ai_usage_logs.latency_ms`).
- Dev-machine numbers are indicative, not a production SLA; re-run the probe
  against the production stack after deployment.
- Autosave uses optimistic concurrency with row locking; the P95 includes the
  lock + write + revision bump.
