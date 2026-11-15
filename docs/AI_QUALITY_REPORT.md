# AI Quality Evaluation Report

**Date:** 2026-11-15 (Slice 11b)
**Harness:** `backend/scripts/eval_ai.py` + `backend/scripts/verify_llm.py`
**Raw reports:** `test-results/ai-eval/`

## Status: pipeline verified; REAL quality pending the provider key

The evaluation harness runs representative datasets against the configured
provider and records model, prompt version, latency, tokens and estimated
cost per call. It currently covers `grammar_deep_check_v1` (10 cases) and
`teaching_v1` (5 cases); expression/evaluation/rewrite datasets extend the
same harness.

### Mock run (harness validation ONLY — not quality evidence)

```
LLM_PROVIDER=mock python scripts/eval_ai.py
grammar_deep_check_v1: accuracy 0.500, precision 0.500, recall 1.000 (10 cases, 0 errors)
teaching_v1:           mean_rubric_score 0.750 (5 cases, 0 errors)
LLM calls: 15, estimated cost: 0.0
```

The mock provider always confirms fragments and emits placeholder teaching,
so these numbers validate the **plumbing** (schema validation, metrics,
usage logging, report generation) — they are **not** evidence of linguistic
quality. The harness explicitly warns when run with mock.

## Blocked on user action

**Re-checked 2026-11-15 (takeover session):** `.env` still has
`LLM_PROVIDER=deepseek`, `LLM_BASE_URL=https://api.deepseek.com`,
`LLM_MODEL=deepseek-flash`, but `LLM_API_KEY` is **empty** — real quality
evaluation remains blocked. The mock harness was re-run the same day
(15 calls, 0 errors, report `eval-mock-20261115-111416.json`), confirming the
pipeline still works end to end.

Real quality evaluation requires the rotated DeepSeek key in `.env`
(`LLM_API_KEY`). The credential exposed in chat was **never used** (user
security directive). Once the key is set:

```
cd backend
.venv\Scripts\python.exe scripts\verify_llm.py     # connectivity + model check
.venv\Scripts\python.exe scripts\eval_ai.py        # real quality metrics
```

## Quality gates to run before launch (with the real provider)
- Grammar deep-check precision/recall/false-positive rate on the dataset.
- Teaching rubric score (contextual, grounded in the user's sentence — ADR-015).
- IELTS evaluation consistency vs. human bands; rewrite semantic preservation.
- RAG Recall@K / MRR with a real embedding endpoint (mock vectors are not
  semantic).
- Record model + prompt versions with every result (already enforced via
  `ai_usage_logs` and the prompt registry).
