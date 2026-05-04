from __future__ import annotations

import asyncio

from .reconciler import run_reconciliation_cycle


def main() -> None:
    asyncio.run(run_reconciliation_cycle())


if __name__ == "__main__":
    main()
