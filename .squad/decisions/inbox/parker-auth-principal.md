# 2026-05-07T23:33:42.986+02:00 — Parker auth principal fix

**Requested by:** Kiko de Angel

## Context
- Front Door + Easy Auth was authenticating successfully, but `/dashboard` and Upload Web API routes could still return 401 because they depended on `X-MS-TOKEN-AAD-ID-TOKEN`.
- In this environment the token store is not configured, so the ID token header is not guaranteed to exist.

## Decision
1. Treat `X-MS-CLIENT-PRINCIPAL` as the primary Easy Auth identity source.
2. If that header is missing or incomplete, fall back to `X-MS-CLIENT-PRINCIPAL-ID` + `X-MS-CLIENT-PRINCIPAL-NAME`.
3. Keep `X-MS-TOKEN-AAD-ID-TOKEN` only as a legacy compatibility fallback.
4. Reuse the same Easy Auth header parsing for both Upload Web middleware sessions and shared API dependencies so HTML pages and API endpoints resolve the same user identity.

## Notes
- `X-MS-CLIENT-PRINCIPAL` must be base64-decoded and parsed as JSON before claim extraction.
- Group/role claims from the principal payload should continue to hydrate `AuthenticatedUser.groups`.
- Requested pytest command still stops on an unrelated pre-existing `tests/unit/test_learning.py` import error (`SequentialBuilder` missing from `agent_framework`).
