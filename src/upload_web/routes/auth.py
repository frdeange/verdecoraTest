from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from src.upload_web.middleware.session_security import (
    SessionSecurityManager,
    build_logout_redirect,
)

router = APIRouter(tags=["upload-web-auth"])


@router.get("/logout", include_in_schema=False)
async def logout(reason: str | None = Query(default=None)) -> RedirectResponse:
    response = RedirectResponse(url=build_logout_redirect(reason), status_code=307)
    SessionSecurityManager.clear_session_cookie(response)
    return response
