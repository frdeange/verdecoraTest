from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from .entra import AuthenticatedUser, EntraAuthError, build_authenticated_user


async def get_current_user(
    x_ms_token_aad_id_token: Annotated[str | None, Header(alias="X-MS-TOKEN-AAD-ID-TOKEN")] = None,
) -> AuthenticatedUser:
    """Return the authenticated Easy Auth user from the Entra ID token header."""

    if x_ms_token_aad_id_token is None or not x_ms_token_aad_id_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-MS-TOKEN-AAD-ID-TOKEN header.",
        )

    try:
        return build_authenticated_user(x_ms_token_aad_id_token)
    except EntraAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
