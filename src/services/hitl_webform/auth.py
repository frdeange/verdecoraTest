from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, status
from pydantic import BaseModel

from src.shared.auth.entra import EntraAuthError, extract_name

from .config import HITLWebformConfig
from .security import EntraTokenValidator, TokenClaims, TokenValidationError, extract_bearer_token


class AuthenticatedReviewer(BaseModel):
    email: str
    subject: str
    display_name: str
    roles: tuple[str, ...] = ()


@lru_cache(maxsize=8)
def get_token_validator(tenant_id: str, expected_audience: str) -> EntraTokenValidator:
    return EntraTokenValidator(tenant_id=tenant_id, client_id=expected_audience)


def _build_authenticated_reviewer(claims: TokenClaims) -> AuthenticatedReviewer:
    try:
        display_name = extract_name(claims.raw_claims)
    except EntraAuthError:
        display_name = claims.email.split("@", maxsplit=1)[0].replace(".", " ").title()
    return AuthenticatedReviewer(
        email=claims.email,
        subject=claims.subject,
        display_name=display_name,
        roles=claims.roles,
    )


async def validate_entra_token(
    authorization_header: str | None,
    *,
    config: HITLWebformConfig,
) -> AuthenticatedReviewer:
    if authorization_header is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")

    try:
        token = extract_bearer_token(authorization_header)
    except TokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if config.allow_local_email_bearer and "@" in token:
        local_part = token.split("@", maxsplit=1)[0]
        return AuthenticatedReviewer(email=token.casefold(), subject=token, display_name=local_part.title())

    validator = get_token_validator(config.tenant_id, config.expected_audience)
    try:
        claims = await validator.validate_token(token)
    except TokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if not validator.require_role(claims, config.reviewer_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The reviewer is missing the required HITL role.",
        )

    return _build_authenticated_reviewer(claims)
