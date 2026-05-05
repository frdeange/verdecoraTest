# Burke — Store catalog decision

- **Date:** 2026-05-05
- **Owner:** Burke
- **Issue:** #91 / UW-71
- **Requested by:** Kiko de Angel

## Decision
Use a single JSON-backed Verdecora store catalog as the shared source for Upload Web store detection and future Business Central location seeding.

## Catalog decision
1. Keep one canonical record per physical store in `data/stores/verdecora-stores.json`.
2. Include human-facing aliases for OCR/store-detection matching, but keep a separate BC-friendly `bc_location_code` for future `Location` creation.
3. Seed BC from the shared catalog through a dry-run script first; connect the real MCP write path in a later sprint after BC location governance is confirmed.

## Why
This keeps the Upload Web and BC integration aligned on the same store master data while respecting BC as the system of record for operational location setup. Separating aliases from short BC location codes reduces matching ambiguity and avoids pushing overly long or accent-sensitive names into BC master data.
