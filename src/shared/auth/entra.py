from __future__ import annotations

import base64
import binascii
import json
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
CLIENT_PRINCIPAL_HEADER = "X-MS-CLIENT-PRINCIPAL"
CLIENT_PRINCIPAL_ID_HEADER = "X-MS-CLIENT-PRINCIPAL-ID"
CLIENT_PRINCIPAL_NAME_HEADER = "X-MS-CLIENT-PRINCIPAL-NAME"
CLIENT_PRINCIPAL_IDP_HEADER = "X-MS-CLIENT-PRINCIPAL-IDP"
LEGACY_ID_TOKEN_HEADER = "X-MS-TOKEN-AAD-ID-TOKEN"
CLIENT_PRINCIPAL_CLAIM_MAP = {
    "name": "name",
    "preferred_username": "preferred_username",
    "email": "email",
    "upn": "upn",
    "oid": "oid",
    "http://schemas.microsoft.com/identity/claims/objectidentifier": "oid",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": "oid",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "email",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": "name",
    "groups": "groups",
    "roles": "groups",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": "groups",
}


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


def build_authenticated_user_from_easy_auth_headers(headers: ClaimsMapping) -> AuthenticatedUser:
    user = _build_authenticated_user_from_client_principal_headers(headers)
    if user is not None:
        return user

    legacy_id_token = _clean_header_value(headers.get(LEGACY_ID_TOKEN_HEADER))
    if legacy_id_token is None:
        raise EntraAuthError("Missing Easy Auth authentication headers.")

    return build_authenticated_user(legacy_id_token)


def _build_authenticated_user_from_client_principal_headers(headers: ClaimsMapping) -> AuthenticatedUser | None:
    principal_name = _clean_header_value(headers.get(CLIENT_PRINCIPAL_NAME_HEADER))
    principal_id = _clean_header_value(headers.get(CLIENT_PRINCIPAL_ID_HEADER))
    principal_idp = _clean_header_value(headers.get(CLIENT_PRINCIPAL_IDP_HEADER))
    client_principal = _clean_header_value(headers.get(CLIENT_PRINCIPAL_HEADER))

    if client_principal is not None:
        claims = decode_client_principal_claims(client_principal)
        if principal_id is not None:
            claims.setdefault("oid", principal_id)
        if principal_name is not None:
            claims.setdefault("name", principal_name)
            claims.setdefault("preferred_username", principal_name)
        if principal_idp is not None:
            claims.setdefault("idp", principal_idp)
        return AuthenticatedUser(
            oid=extract_oid(claims),
            name=extract_name(claims),
            groups=extract_groups(claims),
            claims=claims,
        )

    if principal_name is None or principal_id is None:
        return None

    claims: dict[str, Any] = {
        "oid": principal_id,
        "name": principal_name,
        "preferred_username": principal_name,
    }
    if principal_idp is not None:
        claims["idp"] = principal_idp

    return AuthenticatedUser(oid=principal_id, name=principal_name, groups=(), claims=claims)


def _normalize_claims(
    raw_claims: list[Any],
    name_claim_type: str | None,
    role_claim_type: str | None,
) -> dict[str, Any]:
    """Extract and normalize claims from the Easy Auth client principal."""
    normalized: dict[str, Any] = {}
    groups: list[str] = []

    for raw_claim in raw_claims:
        if not isinstance(raw_claim, dict):
            continue
        claim_type = _clean_header_value(raw_claim.get("typ"))
        claim_value = _clean_header_value(raw_claim.get("val"))
        if claim_type is None or claim_value is None:
            continue

        if claim_type == name_claim_type and "name" not in normalized:
            normalized["name"] = claim_value

        mapped_claim_name = CLIENT_PRINCIPAL_CLAIM_MAP.get(claim_type)
        if mapped_claim_name == "groups" or claim_type == role_claim_type:
            groups.append(claim_value)
            continue
        if mapped_claim_name is not None and mapped_claim_name not in normalized:
            normalized[mapped_claim_name] = claim_value

    if groups:
        normalized["groups"] = groups
    return normalized


def decode_client_principal_claims(encoded_principal: str) -> dict[str, Any]:
    padded_principal = encoded_principal + "=" * (-len(encoded_principal) % 4)
    try:
        decoded_bytes = base64.b64decode(padded_principal.encode("utf-8"))
        decoded_json = json.loads(decoded_bytes.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntraAuthError("The Easy Auth client principal could not be decoded.") from exc

    if not isinstance(decoded_json, dict):
        raise EntraAuthError("The Easy Auth client principal did not contain a valid claim set.")

    raw_claims = decoded_json.get("claims")
    if not isinstance(raw_claims, list):
        raise EntraAuthError("The Easy Auth client principal is missing claims.")

    name_claim_type = _clean_header_value(decoded_json.get("name_typ"))
    role_claim_type = _clean_header_value(decoded_json.get("role_typ"))
    normalized_claims = _normalize_claims(raw_claims, name_claim_type, role_claim_type)

    auth_type = _clean_header_value(decoded_json.get("auth_typ"))
    if auth_type is not None:
        normalized_claims["auth_typ"] = auth_type

    return normalized_claims


def _clean_header_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned_value = value.strip()
    return cleaned_value or None
