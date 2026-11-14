# Missing Dependency — System Design V1.1

**Status:** MISSING — not available in the workspace
**Recorded during:** Stage 0 preparation (approved decisions A–G)
**Action taken:** Recorded only. No content reconstructed, inferred or substituted.

## 1. What is missing

`AGENTS.md` section 1 names **System Design V1.1** as part of the approved engineering
baseline, and section 5 expects it at `docs/SYSTEM_DESIGN.md`.

No System Design document exists anywhere in the workspace. The preflight inspection
covered the project root and all subdirectories. Nothing equivalent was found.

Therefore `docs/SYSTEM_DESIGN.md` **does not exist** and is deliberately not created.

## 2. Why it is not fabricated

`AGENTS.md` section 1 states:

> If a document is missing, do not invent its contents; report the missing dependency.

Per approved decision **G**, System Design V1.1 is recorded as a missing dependency.
No attempt is made to rebuild or guess its contents.

## 3. Available approved baselines

| Baseline | Version | Location | State |
|---|---|---|---|
| Product Requirements | PRD V1.1 | `docs/PRD_V1.1.docx` | Present (DOCX only) |
| System Design | V1.1 | — | **MISSING** |
| Database ERD | V1.2 | `docs/DATABASE_ERD.md` | Present |
| API Specification | V1.1, revision V1.1.1 | `docs/API_SPECIFICATION.md` | Present |
| OpenAPI contract | 3.1, `info.version` 1.1.1 | `contracts/openapi.yaml` | Present |

## 4. Impact

The Stage 1 bootstrap does not depend on System Design V1.1: its scope is fixed by
`AGENTS.md` section 10 and `docs/MONOREPO_INITIALIZATION_TASKS.md`.

Features that would require architectural decisions normally documented in System
Design V1.1 must not be implemented until the approved document is supplied. This
includes authentication flows, AI provider abstraction, grammar-checking pipeline
design, workflow orchestration and any module boundary beyond the bootstrap.

## 5. Required follow-up

Supply the approved **System Design V1.1** and place it at `docs/SYSTEM_DESIGN.md`.
Until then, this file is the authoritative record of the gap.