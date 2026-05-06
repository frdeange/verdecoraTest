# Vasquez decision — upload-web smoke auth assumptions

- Date: 2026-05-05
- Issue: #99 / UW-17

## Decision

Treat the upload web landing page (`/`) as Easy Auth protected in smoke coverage, and add a placeholder authenticated `POST /api/sessions` route so auth checks can be exercised end-to-end.

## Why

The requested smoke suite explicitly expects unauthenticated access to `/` to be rejected and `/api/sessions` to require auth. The existing scaffold had no session route and rendered `/` anonymously, so the minimal product change keeps smoke coverage aligned with the acceptance criteria.
