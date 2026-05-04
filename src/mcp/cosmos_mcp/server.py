from __future__ import annotations

from functools import lru_cache
from typing import Any

from azure.cosmos import ContainerProxy, CosmosClient, DatabaseProxy, exceptions
from mcp.server.fastmcp import FastMCP

from src.mcp.common import MCPServerError, MCPValidationError, get_default_credential, require_env
from src.mcp.cosmos_mcp.models import CosmosQueryParameter

mcp = FastMCP("verdecora-cosmos-mcp", json_response=True)


class CosmosMCPError(MCPServerError):
    """Base error for Cosmos MCP operations."""


class CosmosOperationError(CosmosMCPError):
    """Raised when a Cosmos DB operation fails."""


@lru_cache(maxsize=1)
def get_cosmos_client() -> CosmosClient:
    """Create a cached Cosmos DB client authenticated with managed identity."""

    return CosmosClient(url=require_env("COSMOS_ENDPOINT"), credential=get_default_credential())


def get_database_client(database: str) -> DatabaseProxy:
    """Return a Cosmos database client for the provided database name."""

    if not database.strip():
        raise MCPValidationError("database must not be empty")
    return get_cosmos_client().get_database_client(database)


def get_container_client(database: str, container: str) -> ContainerProxy:
    """Return a Cosmos container client for the provided database and container names."""

    if not container.strip():
        raise MCPValidationError("container must not be empty")
    return get_database_client(database).get_container_client(container)


@mcp.tool()
def read_document(database: str, container: str, document_id: str, partition_key: str) -> dict[str, Any]:
    """Read a single document from Cosmos DB."""

    if not document_id.strip():
        raise MCPValidationError("document_id must not be empty")
    if not partition_key.strip():
        raise MCPValidationError("partition_key must not be empty")

    try:
        document = get_container_client(database, container).read_item(item=document_id, partition_key=partition_key)
    except exceptions.CosmosResourceNotFoundError as exc:
        raise CosmosOperationError(f"Document '{document_id}' was not found in '{database}/{container}'.") from exc
    except exceptions.CosmosHttpResponseError as exc:
        raise CosmosOperationError(f"Failed to read document '{document_id}': {exc.message}") from exc

    return dict(document)


@mcp.tool()
def query_documents(
    database: str,
    container: str,
    query: str,
    parameters: list[CosmosQueryParameter] | None = None,
) -> list[dict[str, Any]]:
    """Execute a Cosmos DB SQL query and return the matching documents."""

    if not query.strip():
        raise MCPValidationError("query must not be empty")

    cosmos_parameters = [parameter.model_dump() for parameter in parameters or []]

    try:
        items = get_container_client(database, container).query_items(
            query=query,
            parameters=cosmos_parameters,
            enable_cross_partition_query=True,
        )
    except exceptions.CosmosHttpResponseError as exc:
        raise CosmosOperationError(f"Failed to execute query against '{database}/{container}': {exc.message}") from exc

    return [dict(item) for item in items]


@mcp.tool()
def upsert_document(database: str, container: str, document: dict[str, Any]) -> dict[str, Any]:
    """Create or update a document in Cosmos DB."""

    document_id = str(document.get("id", "")).strip()
    if not document_id:
        raise MCPValidationError("document must include a non-empty 'id' field")

    try:
        response = get_container_client(database, container).upsert_item(body=document)
    except exceptions.CosmosHttpResponseError as exc:
        raise CosmosOperationError(f"Failed to upsert document '{document_id}': {exc.message}") from exc

    return dict(response)


@mcp.tool()
def delete_document(database: str, container: str, document_id: str, partition_key: str) -> bool:
    """Delete a single document from Cosmos DB."""

    if not document_id.strip():
        raise MCPValidationError("document_id must not be empty")
    if not partition_key.strip():
        raise MCPValidationError("partition_key must not be empty")

    try:
        get_container_client(database, container).delete_item(item=document_id, partition_key=partition_key)
    except exceptions.CosmosResourceNotFoundError:
        return False
    except exceptions.CosmosHttpResponseError as exc:
        raise CosmosOperationError(f"Failed to delete document '{document_id}': {exc.message}") from exc

    return True


def main() -> None:
    """Run the Cosmos MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
