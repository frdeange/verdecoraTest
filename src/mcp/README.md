# Custom MCP Servers

Custom MCP (Model Context Protocol) server implementations for the Verdecora AI Agents project.

## Shared conventions

- Python 3.12+
- `mcp.server.fastmcp.FastMCP`
- Azure Managed Identity via `DefaultAzureCredential`
- No shared keys or connection strings

## Servers

### `cosmos_mcp`

Cosmos DB read/write server backed by `azure-cosmos`.

**Configuration**
- `COSMOS_ENDPOINT`

**Tools**
- `read_document(database, container, document_id, partition_key)`
- `query_documents(database, container, query, parameters)`
- `upsert_document(database, container, document)`
- `delete_document(database, container, document_id, partition_key)`

Run with:

```bash
python -m src.mcp.cosmos_mcp.server
```

### `content_understanding_mcp`

Document Intelligence wrapper backed by `azure-ai-documentintelligence`.

**Configuration**
- `DOCINTELL_ENDPOINT`

**Tools**
- `analyze_document(document_url_or_base64, model_id='prebuilt-layout')`
- `analyze_invoice(document_url_or_base64)`
- `extract_tables(document_url_or_base64)`
- `extract_key_value_pairs(document_url_or_base64)`

Run with:

```bash
python -m src.mcp.content_understanding_mcp.server
```

### `feature_flags_mcp`

Cosmos-backed feature flag and supplier configuration server.

**Configuration**
- `COSMOS_ENDPOINT`

**Storage**
- Database: `verdecora-config`
- Container: `feature-flags`

**Tools**
- `get_flag(flag_name, context=None)`
- `set_flag(flag_name, value, description=None)`
- `list_flags(prefix=None)`
- `get_supplier_config(supplier_id)`

Run with:

```bash
python -m src.mcp.feature_flags_mcp.server
```

### `bc_mcp`

Async client wrapper for the native Business Central MCP endpoint.

**Configuration**
- `BC_MCP_SERVER_URL`
- `BC_MCP_TENANT_ID`
- `BC_MCP_ENVIRONMENT_NAME`
- `BC_MCP_COMPANY`
- `BC_MCP_CONFIGURATION_NAME`
- `BC_MCP_SCOPE`

**Highlights**
- Native MCP over streamable HTTP
- `DefaultAzureCredential` bearer auth
- Read helpers for vendors, purchase orders, PO lines, items, and purchase receipts
- Configurable write-side tool mappings for receipt posting flows
