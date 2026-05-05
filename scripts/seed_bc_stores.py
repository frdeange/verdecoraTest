from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if TYPE_CHECKING:
    from src.models.store import Store

logger = logging.getLogger(__name__)


class BCLocationSeed(BaseModel):
    """Minimum Business Central Location payload needed for future MCP creation.

    BC Location is the master record used to route receipts and inventory by physical site.
    For this seed we keep the fields intentionally small and BC-friendly: a short code,
    display name, address, city, county/region, and post code.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    address: str
    city: str
    county: str
    post_code: str


class MockBCLocationMCPClient:
    """Dry-run stub for the future Business Central MCP write path."""

    def create_location(self, payload: BCLocationSeed, *, dry_run: bool = True) -> dict[str, Any]:
        action = "Would create" if dry_run else "Create requested"
        logger.info(
            "%s BC Location %s (%s) | %s, %s %s | county=%s",
            action,
            payload.code,
            payload.name,
            payload.address,
            payload.city,
            payload.post_code,
            payload.county,
        )
        return {"dry_run": dry_run, "location": payload.model_dump()}


def to_bc_location(store: Store) -> BCLocationSeed:
    """Map the shared store catalog to the BC Location shape expected by the stub."""

    return BCLocationSeed(
        code=store.bc_location_code,
        name=store.name,
        address=store.address,
        city=store.city,
        county=store.region,
        post_code=store.postal_code,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Verdecora stores into BC Location master data.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Reserved for a future sprint. The current stub still performs a dry run.",
    )
    return parser.parse_args()


def main() -> int:
    from src.shared.stores.loader import load_stores

    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    stores = load_stores()
    client = MockBCLocationMCPClient()
    dry_run = not args.execute

    logger.info("Loaded %s stores from the shared catalog.", len(stores))
    if args.execute:
        logger.info("--execute was requested, but BC write mode is intentionally stubbed in this sprint.")

    for store in stores:
        client.create_location(to_bc_location(store), dry_run=dry_run)

    logger.info("BC store seed completed in dry-run mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
