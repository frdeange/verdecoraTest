from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient
from pydantic import BaseModel, ConfigDict, Field

REVIEWER_ROLE = "Verdecora.StoreManager"


class TokenValidationError(RuntimeError):
    """Raised when an Entra access token cannot be trusted."""


class TokenClaims(BaseModel):
    """Normalized claims extracted from an Entra access token."""

    model_config = ConfigDict(frozen=True)

    subject: str = Field(alias="sub")
    issuer: str = Field(alias="iss")
    audience: str | list[str] = Field(alias="aud")
    email: str
    roles: tuple[str, ...] = ()
    raw_claims: dict[str, Any] = Field(default_factory=dict)


def extract_bearer_token(authorization_header: str) -> str:
    """Extract the JWT from a standard Authorization header value."""

    scheme, _, token = authorization_header.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise TokenValidationError("Expected an Authorization header with the format: Bearer <token>.")
    return token.strip()


class EntraTokenValidator:
    """Validate Entra-issued JWTs for the HITL webform."""

    def __init__(self, tenant_id: str, client_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self.jwks_url = f"{self.issuer}/discovery/v2.0/keys"
        self._jwks_client = PyJWKClient(self.jwks_url)

    async def validate_token(self, token: str) -> TokenClaims:
        """Validate a JWT signature, issuer, and audience through the tenant JWKS endpoint."""

        try:
            signing_key = await asyncio.to_thread(self._jwks_client.get_signing_key_from_jwt, token)
            decoded = await asyncio.to_thread(
                jwt.decode,
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "nbf", "aud", "iss", "sub"]},
            )
        except InvalidTokenError as exc:
            raise TokenValidationError("The Entra access token is invalid or expired.") from exc

        email = self._resolve_email(decoded)
        roles = self._coerce_roles(decoded.get("roles"))
        return TokenClaims.model_validate(
            {
                **decoded,
                "email": email,
                "roles": roles,
                "raw_claims": dict(decoded),
            }
        )

    def require_role(self, claims: TokenClaims, role: str) -> bool:
        """Return whether the validated token carries the required application role."""

        required_role = role.casefold()
        return any(existing_role.casefold() == required_role for existing_role in claims.roles)

    def _resolve_email(self, decoded: Mapping[str, Any]) -> str:
        for candidate_key in ("preferred_username", "email", "upn"):
            candidate = decoded.get(candidate_key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip().casefold()
        raise TokenValidationError("The Entra access token does not contain a usable reviewer email claim.")

    def _coerce_roles(self, roles: Any) -> tuple[str, ...]:
        if roles is None:
            return ()
        if isinstance(roles, str):
            normalized_roles: Sequence[str] = [roles]
        elif isinstance(roles, Sequence) and not isinstance(roles, (bytes, bytearray)):
            normalized_roles = [str(role) for role in roles if str(role).strip()]
        else:
            raise TokenValidationError("The Entra access token contains an invalid roles claim.")
        return tuple(role.strip() for role in normalized_roles if role.strip())
