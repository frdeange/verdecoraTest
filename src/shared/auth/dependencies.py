from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from .entra import (
    LEGACY_ID_TOKEN_HEADER,
    AuthenticatedUser,
    EntraAuthError,
    build_authenticated_user_from_easy_auth_headers,
)


async def get_current_user(
    request: Request,
    _legacy_id_token: Annotated[str | None, Header(alias=LEGACY_ID_TOKEN_HEADER)] = None,
) -> AuthenticatedUser:
    """Return the authenticated Easy Auth user from client principal or legacy token headers."""

    try:
        return build_authenticated_user_from_easy_auth_headers(request.headers)
    except EntraAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
