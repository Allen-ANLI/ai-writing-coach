# ADR-036: 表达润色一致性闭环（判据统一 + 提供前替代回验）

**Status:** Accepted (2026-11-21, user directive)
**Related:** ADR-026/027/028, PRD FR-02.8, contract 1.14.0.

## Context

Two user-reported defects (2026-11-20/21) in fragment polish:

1. **The AI overturns its own polish.** After accepting a polish option, the
   sentence is re-scanned (the frontend resets the scan dedup key and the
   revision bump re-triggers), and the LLM frequently proposes new changes to
   the wording it just produced — sometimes reverting toward the original.
   Root cause: `polish_sentence` had no consistency mechanism between its
   detector and its generator; "natural sentences yield zero fragments" was a
   soft prompt instruction only, and the judge never saw its own output
   substituted back into the sentence.
2. **Copied model-essay text gets polish suggestions.** The planner's model
   essay is AI-generated native-quality text, but the detector's criterion was
   too loose — stylistic rewordings of already-natural text counted as
   "unnatural", so even reference material attracted suggestions.

User directive (2026-11-21): solve at the root — fix the unnaturalness
judgment itself AND make the generator's output consistent with that judgment:
"can what the LLM writes be guaranteed to be recognized as natural when
inserted back?" After being presented with the feasibility analysis (strict
self-consistency of a probabilistic judge is impossible; an engineering closed
loop is achievable) and a three-layer proposal, the user chose **layers 1+2
only, explicitly rejecting the deterministic backstop layer** (judgment cache,
accepted-fragment protection, model-essay provenance suppression, no forced
re-scan).

## Decision

### Layer 1 — one narrowed criterion, shared verbatim (expression_polish v3)

- `_UNNATURAL_CRITERION` (registry constant) defines UNNATURAL operationally:
  genuinely non-native English a native reader would stumble on — Chinglish /
  L1-transfer patterns, wrong collocations, awkward phrasing that breaks normal
  usage. Style, register, tone, vocabulary sophistication, sentence variety
  and personal preference are explicitly NOT problems; plain native-quality
  text (including AI-generated or model-essay text) is NATURAL; when in doubt,
  treat as natural.
- `EXPRESSION_POLISH_V3` embeds the criterion verbatim and aligns the
  generator: each option must be the MINIMAL repair that passes the SAME
  criterion, never an improvement of already-natural wording, with an
  in-generation substitution self-check instruction. v2 stays immutable.

### Layer 2 — substitution re-check before offer (polish_verify v1)

- `polish_sentence` is restructured into three phases:
  1. detect (v3) + validate offsets → collect candidates in memory;
  2. **verify**: every candidate option is substituted back into the sentence
     (`sentence[:start] + option.text + sentence[end:]`), all candidates are
     batched into ONE `polish_verify` v1 call whose system prompt embeds the
     identical `_UNNATURAL_CRITERION`. Per candidate the judge returns
     `original_unnatural` (re-check of its own flag — rejects false positives,
     the model-essay guard) and `option_unnatural` (the fragment region AFTER
     substitution). Only `original_unnatural=true AND option_unnatural=false`
     candidates survive; a fragment with no passing option is dropped;
  3. persist only the verified survivors (suggestions + items), record usage
     for both calls (`expression_polish` v3, `polish_verify` v1).
- **Fail-closed**: a verify failure (provider error, quota guard) records an
  error usage row and returns zero fragments — no unverified option is ever
  shown or persisted.
- Applies to both the automatic scan and the pagination path (more options
  are held to the same consistency bar). Natural sentences produce no
  candidates → no verify call → no extra spend.
- Mock provider: `_mock_polish_verify` parses the candidate block; the flag
  holds iff the original sentence contains "very like", and a substituted
  option is still unnatural iff it leaves "very like" in the sentence — so
  E2E exercises the real verify round-trip deterministically.

## Consequences

- Every offered option has literally passed "insert it back and let the same
  judge re-judge" before the user sees it; false-positive flags (including on
  model-essay text) are re-checked by the same judge before offer.
- Cost: +1 batched LLM call per scan that produces candidates (quota-metered,
  usage-logged); underline latency +1–2s (background, non-blocking). Natural
  sentences and verify-free paths spend nothing extra.
- **Residual risks (accepted by the user's scope decision)**: without the
  deterministic backstop, judge instability can still re-suggest on later
  re-scans of unchanged text (no judgment cache), accepted wording is not
  protected from future suggestions, and model-essay suppression depends on
  the narrowed criterion being honored (no provenance short-circuit). The
  guarantee is "offered options passed the substitution re-check", not "the
  LLM always agrees with itself" — strict self-consistency of a probabilistic
  judge is not technically achievable.
- No HTTP API shape change (same endpoint/schemas); contract 1.14.0 behavioral
  note. No migration. No frontend change.
- Infrastructure hardening (same slice): the LanguageTool client sets
  `trust_env=False` — local Docker infrastructure must never route through a
  system proxy (httpx reads the Windows registry proxy, which may be
  configured but not running; loopback then fails with WinError 10061 and
  grammar silently degrades to custom rules).
- Tests: 8 backend tests (option filtering, false-positive flag rejection,
  all-options-fail drop, fail-closed + error usage, natural-sentence skip,
  dual usage logs v3/v1, pagination verification, mock judge parsing);
  existing polish E2E now exercises the verify round-trip via the mock.