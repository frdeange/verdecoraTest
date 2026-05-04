from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .orchestration import OrchestratorService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    orchestrator = cast(OrchestratorService, request.app.state.orchestrator)
    readiness_payload = await orchestrator.check_readiness()
    status_code = 200 if bool(readiness_payload.get("ready")) else 503
    return JSONResponse(status_code=status_code, content=cast(dict[str, Any], readiness_payload))
