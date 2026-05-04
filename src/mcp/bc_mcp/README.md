# Business Central native MCP client

This package wraps the native Business Central MCP server exposed at `https://mcp.businesscentral.dynamics.com`.

## Default tenant configuration

- Tenant ID: `562029ef-9022-45a6-b255-40cd71ebb2ce`
- Environment: `Production`
- Company: `CRONUS USA, Inc.`
- Configuration: `DefaultMCPKiko`
- Auth scope: `https://mcp.businesscentral.dynamics.com/.default`

## Supported operations

### Read
- `list_vendors`
- `get_vendor`
- `list_purchase_orders`
- `get_purchase_order`
- `get_po_lines`
- `list_items`
- `search_items`
- `list_purchase_receipts`

### Write
- `create_purchase_receipt`
- `create_purchase_receipt_line`
- `post_purchase_receipt`

## Authentication

The client acquires a bearer token with `DefaultAzureCredential` and uses the MCP Python SDK over the streamable HTTP transport. Override the `BC_MCP_*` environment variables when a tenant exposes different tool names or a more restricted write-side configuration.

> Note: CRONUS validation confirmed read-side receipt APIs and `ReceiveAndInvoice_PurchaseOrders_PAG30066`; write-side purchase-receipt tool names may need tenant-specific overrides.
