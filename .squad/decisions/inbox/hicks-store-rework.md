# Hicks — Store rework delivered

**Date:** 2026-05-05
**Related:** #89, #91, PRs #127 and #128, Ripley sprint 0 review

## Decision
Reworked the rejected store heuristic and store catalog branches onto a clean branch from `origin/master` as `squad/89-91-store-rework`.

## What was preserved
- Burke's canonical `Store` model, JSON-backed 27-store catalog, cached loader, BC seed dry-run script, and catalog validation tests.
- Bishop's address-detection heuristic: Unicode normalization, punctuation stripping, postal-code exact match, fuzzy city/street scoring, and the `StoreMatch` + `detect_store(extracted_address: str, stores: list[Store])` contract.

## What changed in the rework
- Removed the hardcoded `VERDECORA_STORES` list from `src/upload_web/services/store_detector.py`.
- Refactored the detector to consume `src.models.store.Store` and `src.shared.stores.loader.load_stores()`.
- Kept Parker's `src/upload_web/__init__.py` and `src/shared/__init__.py` unchanged; added `src/upload_web/services/__init__.py` only because it was missing on master.
- Adapted detector tests to validate the canonical catalog IDs and shared-loader path.

## Validation
- `python -m pytest tests/unit/test_store_catalog.py tests/unit/test_store_detector.py -q`
- `python -m ruff check src/models/store.py src/shared/stores/ src/upload_web/services/store_detector.py`

## Delivery note
GitHub write actions may still fail under the current EMU authentication context, but the code rework and local validation are complete in the clean branch/worktree.
