from __future__ import annotations

import asyncio

from .analyzer import run_learning_cycle


def main() -> None:
    asyncio.run(run_learning_cycle())


if __name__ == "__main__":
    main()
