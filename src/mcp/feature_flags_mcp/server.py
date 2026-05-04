from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from time import monotonic
from typing import Any

from azure.cosmos import ContainerProxy, CosmosClient, exceptions
from mcp.server.fastmcp import FastMCP

from src.mcp.common import MCPServerError, MCPValidationError, get_default_credential, require_env
from src.mcp.feature_flags_mcp.models import FlagOverride, FlagValue, SupplierConfig

mcp = FastMCP("verdecora-feature-flags-mcp", json_response=True)

CONFIG_DATABASE = "verdecora-config"
FLAGS_CONTAINER = "feature-flags"
FLAG_DOCUMENT_TYPE = "feature-flag"
SUPPLIER_CONFIG_DOCUMENT_TYPE = "supplier-config"
CACHE_TTL_SECONDS = 60.0

_cache: dict[str, tuple[float, FlagValue | SupplierConfig]] = {}


class FeatureFlagsMCPError(MCPServerError):
    """Base error for feature flag operations."""


class FeatureFlagNotFoundError(FeatureFlagsMCPError):
    """Raised when a requested feature flag or supplier config does not exist."""


class FeatureFlagsOperationError(FeatureFlagsMCPError):
    """Raised when Cosmos-backed feature flag operations fail."""


@lru_cache(maxsize=1)
def get_cosmos_client() -> CosmosClient:
    """Create a cached Cosmos DB client authenticated with managed identity."""

    return CosmosClient(url=require_env("COSMOS_ENDPOINT"), credential=get_default_credential())


def get_flags_container() -> ContainerProxy:
    """Return the shared Cosmos container used for feature flags and supplier configs."""

    database = get_cosmos_client().get_database_client(CONFIG_DATABASE)
    return database.get_container_client(FLAGS_CONTAINER)


def cache_key(prefix: str, identifier: str) -> str:
    """Build an in-memory cache key."""

    return f"{prefix}:{identifier}"


def read_cached(key: str) -> FlagValue | SupplierConfig | None:
    """Read a value from the in-memory cache when it is still fresh."""

    cached_entry = _cache.get(key)
    if not cached_entry:
        return None

    expires_at, value = cached_entry
    if monotonic() >= expires_at:
        _cache.pop(key, None)
        return None
    return value


def write_cached(key: str, value: FlagValue | SupplierConfig) -> None:
    """Store a value in the in-memory cache."""

    _cache[key] = (monotonic() + CACHE_TTL_SECONDS, value)


def invalidate_flag_cache(flag_name: str) -> None:
    """Remove cached flag values that match the provided flag name."""

    _cache.pop(cache_key(FLAG_DOCUMENT_TYPE, flag_name), None)


def document_matches_context(override: FlagOverride, context: dict[str, Any]) -> bool:
    """Return whether a contextual override applies to the provided request context."""

    return all(context.get(key) == value for key, value in override.match.items())


def query_single_document(query: str, parameters: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute a query and return the first matching document."""

    try:
        items = list(
            get_flags_container().query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
    except exceptions.CosmosHttpResponseError as exc:
        raise FeatureFlagsOperationError(f"Feature flag query failed: {exc.message}") from exc

    if not items:
        raise FeatureFlagNotFoundError("No matching document found.")
    return dict(items[0])


def to_flag_value(document: dict[str, Any]) -> FlagValue:
    """Convert a stored feature flag document into a typed model."""

    return FlagValue(
        flag_name=str(document.get("flag_name", document.get("id", ""))),
        value=document.get("value"),
        description=document.get("description"),
        version=int(document.get("version", 1)),
        overrides=[FlagOverride.model_validate(override) for override in document.get("overrides", [])],
        updated_at=document.get("updated_at"),
    )


def to_supplier_config(document: dict[str, Any]) -> SupplierConfig:
    """Convert a stored supplier config document into a typed model."""

    return SupplierConfig(
        supplier_id=str(document.get("supplier_id", document.get("id", ""))),
        configuration=document.get("configuration", {}),
        description=document.get("description"),
        updated_at=document.get("updated_at"),
    )


def invalidate_supplier_config_cache(supplier_id: str) -> None:
    """Remove cached supplier configuration values."""

    _cache.pop(cache_key(SUPPLIER_CONFIG_DOCUMENT_TYPE, supplier_id), None)


@mcp.tool()
def get_flag(flag_name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a feature flag, applying the first matching override for the provided context."""

    normalized_flag_name = flag_name.strip()
    if not normalized_flag_name:
        raise MCPValidationError("flag_name must not be empty")

    cached = read_cached(cache_key(FLAG_DOCUMENT_TYPE, normalized_flag_name))
    flag = cached if isinstance(cached, FlagValue) else None
    if flag is None:
        document = query_single_document(
            "SELECT TOP 1 * FROM c WHERE c.document_type = @document_type AND c.flag_name = @flag_name",
            [
                {"name": "@document_type", "value": FLAG_DOCUMENT_TYPE},
                {"name": "@flag_name", "value": normalized_flag_name},
            ],
        )
        flag = to_flag_value(document)
        write_cached(cache_key(FLAG_DOCUMENT_TYPE, normalized_flag_name), flag)

    effective_value = flag.value
    if context:
        for override in flag.overrides:
            if document_matches_context(override, context):
                effective_value = override.value
                break

    return flag.model_copy(update={"value": effective_value}).model_dump()


@mcp.tool()
def set_flag(flag_name: str, value: Any, description: str | None = None) -> dict[str, Any]:
    """Create or update a feature flag document."""

    normalized_flag_name = flag_name.strip()
    if not normalized_flag_name:
        raise MCPValidationError("flag_name must not be empty")

    timestamp = datetime.now(tz=UTC).isoformat()
    current_version = 0
    try:
        current_flag = get_flag(normalized_flag_name)
        current_version = int(current_flag.get("version", 0))
    except FeatureFlagNotFoundError:
        current_version = 0

    document = {
        "id": normalized_flag_name,
        "flag_name": normalized_flag_name,
        "document_type": FLAG_DOCUMENT_TYPE,
        "value": value,
        "description": description,
        "version": current_version + 1,
        "updated_at": timestamp,
        "overrides": [],
    }

    try:
        response = get_flags_container().upsert_item(body=document)
    except exceptions.CosmosHttpResponseError as exc:
        raise FeatureFlagsOperationError(f"Failed to set flag '{normalized_flag_name}': {exc.message}") from exc

    invalidate_flag_cache(normalized_flag_name)
    return to_flag_value(dict(response)).model_dump()


@mcp.tool()
def list_flags(prefix: str | None = None) -> list[dict[str, Any]]:
    """List feature flags, optionally constrained to a name prefix."""

    query = "SELECT * FROM c WHERE c.document_type = @document_type"
    parameters: list[dict[str, Any]] = [{"name": "@document_type", "value": FLAG_DOCUMENT_TYPE}]
    if prefix:
        query += " AND STARTSWITH(c.flag_name, @prefix)"
        parameters.append({"name": "@prefix", "value": prefix})
    query += " ORDER BY c.flag_name"

    try:
        items = list(
            get_flags_container().query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
    except exceptions.CosmosHttpResponseError as exc:
        raise FeatureFlagsOperationError(f"Failed to list flags: {exc.message}") from exc

    return [to_flag_value(dict(item)).model_dump() for item in items]


@mcp.tool()
def get_supplier_config(supplier_id: str) -> dict[str, Any]:
    """Return the supplier-specific configuration document."""

    normalized_supplier_id = supplier_id.strip()
    if not normalized_supplier_id:
        raise MCPValidationError("supplier_id must not be empty")

    cached = read_cached(cache_key(SUPPLIER_CONFIG_DOCUMENT_TYPE, normalized_supplier_id))
    supplier_config = cached if isinstance(cached, SupplierConfig) else None
    if supplier_config is None:
        document = query_single_document(
            "SELECT TOP 1 * FROM c WHERE c.document_type = @document_type AND c.supplier_id = @supplier_id",
            [
                {"name": "@document_type", "value": SUPPLIER_CONFIG_DOCUMENT_TYPE},
                {"name": "@supplier_id", "value": normalized_supplier_id},
            ],
        )
        supplier_config = to_supplier_config(document)
        write_cached(cache_key(SUPPLIER_CONFIG_DOCUMENT_TYPE, normalized_supplier_id), supplier_config)

    return supplier_config.model_dump()


@mcp.tool()
def set_supplier_config(
    supplier_id: str,
    configuration: dict[str, Any],
    description: str | None = None,
) -> dict[str, Any]:
    """Create or update a supplier-specific configuration document."""

    normalized_supplier_id = supplier_id.strip()
    if not normalized_supplier_id:
        raise MCPValidationError("supplier_id must not be empty")

    timestamp = datetime.now(tz=UTC).isoformat()
    document = {
        "id": normalized_supplier_id,
        "supplier_id": normalized_supplier_id,
        "document_type": SUPPLIER_CONFIG_DOCUMENT_TYPE,
        "configuration": configuration,
        "description": description,
        "updated_at": timestamp,
    }

    try:
        response = get_flags_container().upsert_item(body=document)
    except exceptions.CosmosHttpResponseError as exc:
        raise FeatureFlagsOperationError(
            f"Failed to set supplier config '{normalized_supplier_id}': {exc.message}"
        ) from exc

    invalidate_supplier_config_cache(normalized_supplier_id)
    return to_supplier_config(dict(response)).model_dump()


def main() -> None:
    """Run the feature flags MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
