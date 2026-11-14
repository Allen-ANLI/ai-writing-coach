# Documentation Index and Authority

This directory holds the approved design baselines and task records for AI Writing Coach.

## 1. Single source of truth

**`contracts/openapi.yaml` is the only machine-readable API contract.**

- OpenAPI **3.1.0**, `info.version` **1.1.1**.
- Frontend API type generation and backend contract verification must both read this file.
- There is exactly **one** OpenAPI file in the repository. The former root-level
  `OPENAPI_V1.1.yaml` was **moved** here, not copied, so no stale duplicate exists.
- Do not create additional OpenAPI copies. Do not hand-maintain divergent
  request/response shapes in frontend or backend code.

## 2. Document authority

| Document | Version | Path | Authority |
|---|---|---|---|
| Repository rules | — | `../AGENTS.md` | **Highest.** Constraints for all agents and contributors |
| Product requirements | PRD V1.1 | `PRD_V1.1.docx` | Product scope and intent (DOCX only) |
| System design | V1.1 | `AI_Writing_Coach_System_Design_V1.1.md` | Architecture baseline (user-supplied 2026-11-14, committed in `7baeb36`). `SYSTEM_DESIGN_MISSING.md` is a historical record only |
| Database ERD | V1.2 | `DATABASE_ERD.md` | Schema and data invariants |
| API specification | V1.1, rev V1.1.1 | `API_SPECIFICATION.md` | Human-readable API semantics |
| OpenAPI contract | 3.1 / 1.1.1 | `../contracts/openapi.yaml` | **Machine-readable contract; authoritative for shapes** |
| Traceability matrix | living | `TRACEABILITY_MATRIX.md` | PRD→design→schema→API→code→tests mapping, reconciliation record, completion status |

### Precedence rules

1. `AGENTS.md` overrides everything. Subdirectory `AGENTS.md` files may add constraints
   but must not silently contradict it.
2. For request/response **shapes**, `contracts/openapi.yaml` wins.
3. For **business semantics and invariants**, the ERD and API Specification govern.
4. If the contract and a design document disagree, **stop and report the conflict**.
   Do not silently pick one, and do not change approved business semantics.

## 3. Task and process records

| File | Purpose |
|---|---|
| `MONOREPO_INITIALIZATION_TASKS.md` | V1.0 bootstrap task list (Stage 0 + Stage 1) |
| `CODEX_FIRST_IMPLEMENTATION_TASK.md` | First implementation task instruction |
| `PREFLIGHT_REPORT.md` | Preflight findings and implementation plan |
| `DEVELOPMENT_PLAN.md` | Agreed phase plan |
| `PRD.md` | Provenance record for the PRD DOCX |
| `SYSTEM_DESIGN_MISSING.md` | Historical record (dependency since supplied; see authority table) |
| `TRACEABILITY_MATRIX.md` | Requirement traceability + document reconciliation (Directive V2.0 §1) |

These are process records, not product baselines.

## 4. Contract deviation history (resolved)

The approved V1.1 baseline contained **4 pre-existing validation errors**: three `PATCH`
operations omitted required path parameters
(`/writing-sessions/{session_id}` — `session_id`;
`/essays/{essay_id}/issues/{issue_id}` — `essay_id`, `issue_id`;
`/outlines/{outline_id}` — `outline_id`).

**Resolved 2026-11-14 with explicit user approval**: the missing parameter declarations
were added (additive only; no business semantics changed; `info.version` remains 1.1.1).
Full OpenAPI 3.1 validation now reports **0 errors**, and a structural diff against the
pre-Health baseline confirms no other changes. See `DEVELOPMENT_PLAN.md` tracked item 1.

## 5. V1.1.1 revision scope

The only change to the approved baseline so far is **additive**:

- New endpoint `GET /api/v1/health` (200 database reachable, 503 unavailable).
- New schema `HealthResponse`.
- New tag `Health`.
- New error code `DATABASE_UNAVAILABLE` in `API_SPECIFICATION.md`.
- `info.version` 1.1.0 → 1.1.1.

Verified: zero existing paths changed, zero existing schemas changed, servers, global
security and security schemes unchanged.