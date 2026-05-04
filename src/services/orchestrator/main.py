from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator, cast

from fastapi import FastAPI, HTTPException, Request

from .config import OrchestratorConfig, get_orchestrator_config
from .handler import run_queue_consumer
from .health import router as health_router
from .orchestration import OrchestrationError, OrchestrationRequest, OrchestratorService


class ManualProcessRequest(OrchestrationRequest):
    pass


def create_app(config: OrchestratorConfig | None = None) -> FastAPI:
    resolved_config = config or get_orchestrator_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        orchestrator = OrchestratorService(config=resolved_config)
        stop_event = asyncio.Event()
        consumer_task: asyncio.Task[None] | None = None
        app.state.orchestrator = orchestrator
        app.state.consumer_stop_event = stop_event

        if resolved_config.service_bus_polling_enabled:
            consumer_task = asyncio.create_task(run_queue_consumer(orchestrator, stop_event))
            app.state.consumer_task = consumer_task

        try:
            yield
        finally:
            stop_event.set()
            if consumer_task is not None:
                consumer_task.cancel()
                with suppress(asyncio.CancelledError):
                    await consumer_task
            await orchestrator.close()

    app = FastAPI(title="Verdecora Agentic Orchestrator", lifespan=lifespan)
    app.include_router(health_router)

    @app.post("/process")
    async def process_document(payload: ManualProcessRequest, request: Request) -> dict[str, object]:
        orchestrator = cast(OrchestratorService, request.app.state.orchestrator)
        try:
            result = await orchestrator.process_document(payload)
        except OrchestrationError as exc:
            raise HTTPException(status_code=500, detail=exc.result.model_dump(mode="json")) from exc
        return result.model_dump(mode="json")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("src.services.orchestrator.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
