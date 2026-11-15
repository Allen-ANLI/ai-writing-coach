# ADR-022: Privacy — Password Reset, Account Deletion, Data Export

**Status:** Accepted (Slice 11, 2026-11-15)
**Related:** PRD FR-01 / §9.3, reconciliations R7/R9, contract 1.4.0.

## Context

The PRD requires password reset (FR-01) and privacy controls (§9.3: account
deletion, data export). The baseline contract had none of these (R7/R9 gaps).
Real email delivery and any paid provider require explicit user approval
(Directive §6).

## Decision

1. **Password reset (R7).** `POST /auth/password-reset/request` always returns
   202 (no account enumeration); a single-use token (SHA-256 hash stored,
   60-minute TTL) is delivered through an email provider abstraction. The
   default `console` provider logs the link for development only; activating
   SMTP/API delivery is a launch-blocking decision reserved to the user.
   `POST /auth/password-reset/confirm` validates the token, updates the
   password, and revokes every existing session/refresh token. Both endpoints
   are rate-limited.
2. **Account deletion (R9).** `DELETE /users/me` irreversibly removes the
   account and ALL owned rows in one transaction, children before parents in
   FK-safe order (essay version pointers cleared first to break the
   essays↔versions cycle). System reference data (IELTS bank, subscription
   plans) is never touched. The endpoint is authenticated; deletion is
   user-initiated self-service, not an admin operation.
3. **Data export (R9).** `GET /users/me/export` returns a JSON document of all
   user-owned data (account/profile, essays + documents + versions, sessions,
   expressions + sources + progress, weaknesses, plans/tasks, outlines,
   evaluations/rewrites, workflows, billing, usage logs, session metadata).
   Password hashes and refresh tokens are never exported.
4. **Frontend.** /forgot-password and /reset-password pages; profile "Data &
   privacy" card with JSON download and a two-step confirmed deletion.

## Consequences

- Before production launch: a real email provider must be configured
  (launch checklist, Slice 11) — console delivery is development-only.
- Deletion is immediate and irreversible by design (PRD §9.3); no grace
  period. Backups retain data per the retention policy until they rotate.
- Export is synchronous; very large accounts may need async export later
  (not required at current scale).
