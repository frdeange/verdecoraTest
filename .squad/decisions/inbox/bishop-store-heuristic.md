# Bishop — Store heuristic decision

- **Date:** 2026-05-05
- **Owner:** Bishop
- **Issue:** #89 / UW-04
- **Requested by:** Kiko de Angel

## Decision
Use a deterministic Upload Web preflight heuristic for store suggestion:
1. Normalize extracted address text (lowercase, remove accents, strip punctuation).
2. Prefer exact postal-code matches when the catalog postal code is trusted.
3. Fall back to fuzzy city + street matching using `difflib.SequenceMatcher` plus token overlap.
4. Apply confidence bands from the approved proposal: `>=0.85` auto-select, `0.5-0.85` suggest, `<0.5` no suggestion.

## Catalog decision
For the spike, keep the store catalog hardcoded in Python. Entries with incomplete public address data remain in the catalog, but unverified postal codes stay blank so they cannot trigger false high-confidence auto-selection.

## Why
This keeps the heuristic explainable, cheap, and safe for preflight UX while preserving a clear upgrade path to a canonical catalog source later (BC/AD/assets export).
