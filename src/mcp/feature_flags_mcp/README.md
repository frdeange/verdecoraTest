# Feature Flags MCP Server

FastMCP server for Cosmos-backed feature flags and per-supplier configuration using Azure Managed Identity.

## Configuration

- `COSMOS_ENDPOINT`: Cosmos DB account endpoint.

## Data model

- Database: `verdecora-config`
- Container: `feature-flags`
- Flag documents use `document_type = 'feature-flag'`
- Supplier config documents use `document_type = 'supplier-config'`

## Tools

- `get_flag(flag_name, context=None)`
- `set_flag(flag_name, value, description=None)`
- `list_flags(prefix=None)`
- `get_supplier_config(supplier_id)`

The server keeps a small in-memory cache with a 60 second TTL for reads.

## Run locally

```bash
python -m src.mcp.feature_flags_mcp.server
```
