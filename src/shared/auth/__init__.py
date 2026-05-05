"""Shared Entra authentication helpers."""

from .dependencies import get_current_user
from .entra import (
    AuthenticatedUser,
    EntraAuthError,
    build_authenticated_user,
    decode_jwt,
    extract_groups,
    extract_name,
    extract_oid,
)

__all__ = [
    "AuthenticatedUser",
    "EntraAuthError",
    "build_authenticated_user",
    "decode_jwt",
    "extract_groups",
    "extract_name",
    "extract_oid",
    "get_current_user",
]
