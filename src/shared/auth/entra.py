from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import jwt
from jwt import InvalidTokenError
from pydantic import BaseModel, ConfigDict, Field


class EntraAuthError(ValueError):
    """Raised when Entra claims cannot be extracted from a token."""


class AuthenticatedUser(BaseModel):
    """Normalized uploader identity extracted from an Entra ID token."""

    model_config = ConfigDict(frozen=True)

    oid: str
    name: str
    groups: tuple[str, ...] = ()
    claims: dict[str, Any] = Field(default_factory=dict)


ClaimsMapping = Mapping[str, Any]


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode a JWT without signature verification after Easy Auth has validated it."""

    try:
        decoded = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
            algorithms=["HS256", "RS256"],
        )
    except InvalidTokenError as exc:
        raise EntraAuthError("The Entra ID token could not be decoded.") from exc

    if not isinstance(decoded, dict):
        raise EntraAuthError("The Entra ID token did not contain a valid claim set.")
    return dict(decoded)


def extract_oid(claims: ClaimsMapping) -> str:
    oid = claims.get("oid")
    if isinstance(oid, str) and oid.strip():
        return oid.strip()
    raise EntraAuthError("The Entra ID token is missing the oid claim.")


def extract_name(claims: ClaimsMapping) -> str:
    for claim_name in ("name", "preferred_username", "email", "upn"):
        value = claims.get(claim_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise EntraAuthError("The Entra ID token is missing a usable name claim.")


def extract_groups(claims: ClaimsMapping) -> tuple[str, ...]:
    raw_groups = claims.get("groups")
    if raw_groups is None:
        return ()
    if isinstance(raw_groups, str):
        return (raw_groups.strip(),) if raw_groups.strip() else ()
    if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (bytes, bytearray)):
        return tuple(str(group).strip() for group in raw_groups if str(group).strip())
    raise EntraAuthError("The Entra ID token contains an invalid groups claim.")


def build_authenticated_user(token: str) -> AuthenticatedUser:
    claims = decode_jwt(token)
    return AuthenticatedUser(
        oid=extract_oid(claims),
        name=extract_name(claims),
        groups=extract_groups(claims),
        claims=claims,
    )
