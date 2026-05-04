from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from .config import HITLWebformConfig, get_hitl_webform_config
from .routes import CosmosReviewStore, ServiceBusDecisionPublisher, router


def create_app(
    config: HITLWebformConfig | None = None,
    *,
    review_store: Any | None = None,
    decision_publisher: Any | None = None,
) -> FastAPI:
    resolved_config = config or get_hitl_webform_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.hitl_config = resolved_config
        app.state.review_store = review_store or CosmosReviewStore(resolved_config)
        app.state.decision_publisher = decision_publisher or ServiceBusDecisionPublisher(resolved_config)
        try:
            yield
        finally:
            for attribute in ("review_store", "decision_publisher"):
                resource = getattr(app.state, attribute, None)
                if resource is not None and hasattr(resource, "close"):
                    await resource.close()

    app = FastAPI(title="Verdecora HITL Webform", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("src.services.hitl_webform.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
