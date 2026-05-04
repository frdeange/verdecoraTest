"""Configuration helpers for secure Azure access."""

from .security import get_managed_identity_credential

__all__ = ["get_managed_identity_credential"]
