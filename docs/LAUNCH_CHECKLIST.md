# Launch Checklist

**Rule (Directive V2.0):** no private alpha, public beta, or early-access
release. The product launches once, complete and verified. Items marked
🔒 require explicit user approval; nothing here auto-activates paid services
or deploys publicly.

## Engineering (complete — re-verified 2026-11-15, takeover session)
- [x] All PRD loops implemented (Writing / Learning / Improvement).
- [x] Full API contract implemented — 104/104 operations (1.7.0).
- [x] Reconciliations R1–R12 resolved and documented.
- [x] Backend 391 tests, Playwright 69 E2E, vitest 26 — all green (ADR-026).
- [x] tsc / ESLint / production build (13 routes) / ruff (197 files) clean.
- [x] Migrations 0001–0019 additive; backup/restore round-trip re-verified
      (40 tables, identical row counts; re-verify after 0019 at next drill).
- [x] Structured logging, request tracing, health check, auth + general
      per-IP rate limiting (limiter trip observed live during probing).
- [x] Deployment stack (Dockerfiles + .dockerignore, prod compose validated,
      nginx) defined; image builds verified by CI docker job (dev machine
      cannot reach Docker Hub); runtime-dep closure guarded by test.
- [x] CI pipeline (backend / frontend / E2E / docker build + dependency
      audits) defined; E2E config made cross-platform for Linux runners.
- [x] Security review: pip-audit clean, npm production audit clean
      (8 moderate dev-only lint advisories accepted, documented).
- [x] Performance probe re-run: worst P95 60.1 ms < 500 ms (30 samples).
- [x] Privacy: password reset, account deletion, data export.

## User-gated launch blockers 🔒
- [ ] 🔒 Place the **rotated DeepSeek key** in `.env` (`LLM_API_KEY`). The
      chat-exposed credential must NOT be used. Then run `verify_llm.py` +
      `eval_ai.py` and review AI_QUALITY_REPORT.md.
- [ ] 🔒 Configure a **real embedding endpoint** for semantic quality
      (currently mock pseudo-vectors).
- [ ] 🔒 Approve + configure a **real email provider** (currently console-only;
      password reset emails are not delivered in production until then).
- [ ] 🔒 Approve **real payment activation** (currently sandbox-only; DB CHECK
      constrains provider to 'sandbox').
- [ ] 🔒 Set production secrets: `JWT_SECRET`, `POSTGRES_PASSWORD`, public
      `CORS_ORIGINS` / `FRONTEND_BASE_URL`, TLS termination.
- [ ] 🔒 Approve **public deployment/release** and run the production smoke
      test + perf probe against the live stack.

## Pre-launch verification (after blockers cleared)
- [ ] Real-provider AI quality gates pass (AI_QUALITY_REPORT.md).
- [ ] `scripts/verify_backup.py` PASS on the production database.
- [ ] Production perf probe P95 < 500 ms.
- [ ] Dependency audit (`pip-audit`, `npm audit`) clean.
- [ ] Final full test + E2E run on the release candidate.
