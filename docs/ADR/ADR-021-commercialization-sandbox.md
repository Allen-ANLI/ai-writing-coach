# ADR-021: Commercialization — Sandbox Payments, Quota Metering at the LLM Boundary

**Status:** Accepted (Slice 10, 2026-11-15)
**Related:** Directive §H/§6/§10, PRD G5, reconciliation R8, SD §12.4, contract 1.3.0.

## Context

The product needs plans, entitlements, quotas, metering, a subscription
lifecycle and billing history. The directive forbids purchasing or activating
paid services without explicit approval, so no real payment provider may be
connected yet. Quotas must not penalize pure rule-based checks (SD §12.4:
"pure rule checks are not LLM calls").

## Decision

1. **Sandbox-only payments.** `payment_transactions.provider` is constrained
   to `'sandbox'` at the database level. Checkout creates a pending
   transaction; `POST /billing/confirm` simulates the provider callback and
   activates the subscription. Switching to a real provider is a material
   decision reserved to the user (Directive §6) and will require a new ADR,
   a provider abstraction implementation, and a migration relaxing the CHECK.
2. **Plans as seeded configuration.** free/pro/ultimate are migration-seeded
   rows (deterministic uuid5 ids), not code constants — pricing/quotas can be
   adjusted without code changes. NULL quota means unlimited.
3. **Metering at the LLM boundary.** `llm.record_usage` — the single choke
   point every real LLM call passes through — increments `usage_meters.
   ai_calls`. Rule-only paths never reach it, so they consume no quota.
   Evaluations are additionally counted at queue time. Guards run immediately
   before an LLM call would occur (sync services) or at queue time
   (background flows), returning 429 `QUOTA_EXCEEDED`.
4. **Concurrency-safe counters.** Subscription and meter rows are created
   with `INSERT ... ON CONFLICT DO NOTHING` + re-select; counters increment
   with atomic `UPDATE ... SET x = x + 1`. Page loads fire several billing
   queries concurrently — naive check-then-insert caused unique violations
   (found and fixed via E2E).
5. **Lifecycle.** One subscription per user; free tier materialized lazily.
   Cancel keeps paid access until period end, then rolls back to free on next
   access. Periods are calendar months (UTC), aligned with the meter.
   Idempotency-Key protects checkout/confirm.

## Consequences

- No money moves; the entire commercial surface is testable end-to-end.
- Quota enforcement is best-effort at the boundary: under heavy concurrency a
  few calls may exceed the limit before guards observe the committed counter
  (acceptable; exact pre-authorization would require row locking per call).
- Real-provider activation, webhooks, refunds and tax handling remain future
  work gated on user approval.
