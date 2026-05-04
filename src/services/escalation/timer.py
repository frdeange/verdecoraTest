from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from src.agents.communication_agent import CommunicationAgentService
from src.models.communication import HITLNotification

from .config import EscalationConfig, get_escalation_config
from .scheduler import CosmosEscalationStore, EscalationScheduler


async def run_timer_cycle(
    config: EscalationConfig | None = None, *, now: datetime | None = None
) -> list[HITLNotification]:
    resolved_config = config or get_escalation_config()
    store = CosmosEscalationStore(resolved_config)
    communication_service = CommunicationAgentService(records_container=store)
    scheduler = EscalationScheduler(store, communication_service, config=resolved_config)
    try:
        return await scheduler.run_once(now=now or datetime.now(tz=UTC))
    finally:
        await store.close()


def main() -> None:
    asyncio.run(run_timer_cycle())


if __name__ == "__main__":
    main()
