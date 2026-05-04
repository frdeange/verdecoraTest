# Document Intelligence MCP Server

FastMCP wrapper around Azure AI Document Intelligence using Azure Managed Identity.

## Configuration

- `DOCINTELL_ENDPOINT`: Document Intelligence endpoint.

## Tools

- `analyze_document(document_url_or_base64, model_id='prebuilt-layout')`
- `analyze_invoice(document_url_or_base64)`
- `extract_tables(document_url_or_base64)`
- `extract_key_value_pairs(document_url_or_base64)`

The document input can be an HTTPS URL or a base64-encoded payload.

## Run locally

```bash
python -m src.mcp.content_understanding_mcp.server
```
