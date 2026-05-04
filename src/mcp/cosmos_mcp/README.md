# Cosmos DB MCP Server

FastMCP server for Cosmos DB read/write operations using Azure Managed Identity.

## Configuration

- `COSMOS_ENDPOINT`: Cosmos DB account endpoint.

## Tools

- `read_document(database, container, document_id, partition_key)`
- `query_documents(database, container, query, parameters)`
- `upsert_document(database, container, document)`
- `delete_document(database, container, document_id, partition_key)`

## Run locally

```bash
python -m src.mcp.cosmos_mcp.server
```
