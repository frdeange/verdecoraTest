from __future__ import annotations

import json
from typing import Any

from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult
from pydantic import TypeAdapter

from mcp import ClientSession
from src.mcp.bc_mcp.config import BCMCPSettings, get_bc_mcp_settings
from src.mcp.bc_mcp.models import Item, PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, Vendor
from src.mcp.common import MCPServerError, get_default_credential

_VENDOR_LIST_ADAPTER = TypeAdapter(list[Vendor])
_PURCHASE_ORDER_LIST_ADAPTER = TypeAdapter(list[PurchaseOrder])
_PURCHASE_ORDER_LINE_LIST_ADAPTER = TypeAdapter(list[PurchaseOrderLine])
_ITEM_LIST_ADAPTER = TypeAdapter(list[Item])
_PURCHASE_RECEIPT_LIST_ADAPTER = TypeAdapter(list[PurchaseReceipt])


class BCMCPError(MCPServerError):
    """Base error for Business Central MCP operations."""


class BCMCPInvocationError(BCMCPError):
    """Raised when the Business Central MCP server rejects an operation."""


class BCMCPToolNotAvailableError(BCMCPError):
    """Raised when the configured tool does not exist on the remote server."""


class BCMCPClient:
    """Thin async client around the Business Central native MCP server."""

    def __init__(self, settings: BCMCPSettings | None = None, credential: Any | None = None) -> None:
        self._settings = settings or get_bc_mcp_settings()
        self._credential = credential or get_default_credential()

    @property
    def settings(self) -> BCMCPSettings:
        """Expose the resolved configuration for callers and tests."""

        return self._settings

    def _build_headers(self) -> dict[str, str]:
        """Build authenticated request headers for the streamable HTTP transport."""

        access_token = self._credential.get_token(self._settings.scope)
        return {
            "Authorization": f"Bearer {access_token.token}",
            "x-bc-tenant-id": self._settings.tenant_id,
            "x-bc-environment-name": self._settings.environment_name,
            "x-bc-company": self._settings.company,
            "x-bc-configuration-name": self._settings.configuration_name,
        }

    def _prepare_arguments(self, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Merge per-call arguments with the shared BC tenant/environment context."""

        merged = self._settings.operation_context()
        if arguments:
            merged.update({key: value for key, value in arguments.items() if value is not None})
        return merged

    @staticmethod
    def _unwrap_collection(payload: Any) -> list[dict[str, Any]]:
        """Normalize common list payload shapes returned by the native BC MCP server."""

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("value", "items", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [payload]
        return []

    @staticmethod
    def _parse_tool_result(result: CallToolResult) -> Any:
        """Extract structured JSON content from an MCP tool response."""

        if result.isError:
            raise BCMCPInvocationError("The Business Central MCP server returned an error result.")
        if result.structuredContent is not None:
            return result.structuredContent

        texts = [content.text for content in result.content if getattr(content, "type", None) == "text"]
        if not texts:
            return None

        body = "\n".join(texts).strip()
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    async def _call_operation(self, operation: str, arguments: dict[str, Any] | None = None) -> Any:
        """Execute one logical operation by mapping it to an MCP tool call."""

        tool_name = self._settings.tool_name_for(operation)
        async with streamablehttp_client(
            self._settings.normalized_server_url,
            headers=self._build_headers(),
            timeout=self._settings.request_timeout_seconds,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                available_tools = await session.list_tools()
                if tool_name not in {tool.name for tool in available_tools.tools}:
                    raise BCMCPToolNotAvailableError(f"Configured BC MCP tool '{tool_name}' is not available.")
                result = await session.call_tool(tool_name, arguments=self._prepare_arguments(arguments))
        return self._parse_tool_result(result)

    async def list_available_tools(self) -> list[str]:
        """Return the currently exposed tool names from the remote BC MCP server."""

        async with streamablehttp_client(
            self._settings.normalized_server_url,
            headers=self._build_headers(),
            timeout=self._settings.request_timeout_seconds,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
        return sorted(tool.name for tool in tools.tools)

    async def list_vendors(self, *, filter: str | None = None, top: int = 50) -> list[Vendor]:
        payload = await self._call_operation("list_vendors", {"filter": filter, "top": top})
        return _VENDOR_LIST_ADAPTER.validate_python(self._unwrap_collection(payload))

    async def get_vendor(self, vendor_id_or_number: str) -> Vendor:
        escaped_identifier = vendor_id_or_number.replace("'", "''")
        filter_expression = f"id eq '{escaped_identifier}' or number eq '{escaped_identifier}'"
        vendors = await self.list_vendors(filter=filter_expression, top=1)
        if not vendors:
            raise BCMCPInvocationError(f"Vendor '{vendor_id_or_number}' was not found.")
        return vendors[0]

    async def list_purchase_orders(self, *, filter: str | None = None, top: int = 50) -> list[PurchaseOrder]:
        payload = await self._call_operation("list_purchase_orders", {"filter": filter, "top": top})
        return _PURCHASE_ORDER_LIST_ADAPTER.validate_python(self._unwrap_collection(payload))

    async def get_purchase_order(self, purchase_order_id_or_number: str) -> PurchaseOrder:
        escaped_identifier = purchase_order_id_or_number.replace("'", "''")
        filter_expression = f"id eq '{escaped_identifier}' or number eq '{escaped_identifier}'"
        purchase_orders = await self.list_purchase_orders(filter=filter_expression, top=1)
        if not purchase_orders:
            raise BCMCPInvocationError(f"Purchase order '{purchase_order_id_or_number}' was not found.")
        return purchase_orders[0]

    async def get_po_lines(self, purchase_order_id: str, *, top: int = 200) -> list[PurchaseOrderLine]:
        payload = await self._call_operation("get_po_lines", {"PurchaseOrder_id": purchase_order_id, "top": top})
        return _PURCHASE_ORDER_LINE_LIST_ADAPTER.validate_python(self._unwrap_collection(payload))

    async def list_items(self, *, filter: str | None = None, top: int = 50) -> list[Item]:
        payload = await self._call_operation("list_items", {"filter": filter, "top": top})
        return _ITEM_LIST_ADAPTER.validate_python(self._unwrap_collection(payload))

    async def search_items(self, search_text: str, *, top: int = 25) -> list[Item]:
        escaped = search_text.replace("'", "''")
        filter_expression = f"contains(displayName,'{escaped}') or contains(number,'{escaped}')"
        return await self.list_items(filter=filter_expression, top=top)

    async def list_purchase_receipts(self, *, filter: str | None = None, top: int = 50) -> list[PurchaseReceipt]:
        payload = await self._call_operation("list_purchase_receipts", {"filter": filter, "top": top})
        return _PURCHASE_RECEIPT_LIST_ADAPTER.validate_python(self._unwrap_collection(payload))

    async def create_purchase_receipt(self, payload: dict[str, Any]) -> Any:
        """Invoke the configured write-side MCP tool for a purchase receipt header."""

        return await self._call_operation("create_purchase_receipt", payload)

    async def create_purchase_receipt_line(self, purchase_receipt_id: str, payload: dict[str, Any]) -> Any:
        """Invoke the configured write-side MCP tool for a purchase receipt line."""

        return await self._call_operation(
            "create_purchase_receipt_line",
            {"PurchaseReceipt_id": purchase_receipt_id, **payload},
        )

    async def post_purchase_receipt(self, purchase_order_id: str) -> Any:
        """Post the receipt using the configured native tool (defaults to ReceiveAndInvoice)."""

        return await self._call_operation("post_purchase_receipt", {"id": purchase_order_id})
