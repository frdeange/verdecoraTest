from __future__ import annotations

import os
from functools import lru_cache
from importlib import import_module
from typing import Any


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _load_symbol(module_name: str, symbol_name: str) -> Any:
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Missing optional dependency for Azure security helpers: {module_name}. "
            "Install the Azure SDK packages required by this service before using these helpers."
        ) from exc

    return getattr(module, symbol_name)


@lru_cache(maxsize=1)
def get_managed_identity_credential(client_id: str | None = None) -> Any:
    """Return a cached DefaultAzureCredential for the current workload."""

    default_azure_credential = _load_symbol("azure.identity", "DefaultAzureCredential")
    credential_kwargs: dict[str, Any] = {"exclude_interactive_browser_credential": True}
    resolved_client_id = client_id or os.getenv("AZURE_CLIENT_ID")
    if resolved_client_id:
        credential_kwargs["managed_identity_client_id"] = resolved_client_id
    return default_azure_credential(**credential_kwargs)


def get_keyvault_secret(
    secret_name: str,
    *,
    vault_url: str | None = None,
    credential: Any | None = None,
    version: str | None = None,
) -> str:
    """Fetch a Key Vault secret value using managed identity authentication."""

    secret_client = _load_symbol("azure.keyvault.secrets", "SecretClient")
    client = secret_client(
        vault_url=vault_url or _require_env("KEY_VAULT_URL"),
        credential=credential or get_managed_identity_credential(),
    )

    secret_value = client.get_secret(secret_name, version=version).value
    if secret_value is None:
        raise RuntimeError(f"Secret '{secret_name}' has no value.")
    return str(secret_value)


def get_cosmos_client(*, endpoint: str | None = None, credential: Any | None = None) -> Any:
    """Create a Cosmos DB client authenticated with managed identity."""

    cosmos_client = _load_symbol("azure.cosmos", "CosmosClient")
    return cosmos_client(
        url=endpoint or _require_env("COSMOS_ENDPOINT"),
        credential=credential or get_managed_identity_credential(),
    )


def get_servicebus_client(*, fully_qualified_namespace: str | None = None, credential: Any | None = None) -> Any:
    """Create a Service Bus client authenticated with managed identity."""

    servicebus_client = _load_symbol("azure.servicebus", "ServiceBusClient")
    return servicebus_client(
        fully_qualified_namespace=fully_qualified_namespace or _require_env("SERVICEBUS_FQ_NAMESPACE"),
        credential=credential or get_managed_identity_credential(),
    )
