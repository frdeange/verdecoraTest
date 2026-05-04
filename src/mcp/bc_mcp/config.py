from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field


class BCMCPToolNames(BaseModel):
    """Default tool-name mapping for the native Business Central MCP server."""

    model_config = ConfigDict(extra="forbid")

    list_vendors: str = Field(default_factory=lambda: os.getenv("BC_MCP_TOOL_LIST_VENDORS", "List_Vendors_PAG30010"))
    list_purchase_orders: str = Field(
        default_factory=lambda: os.getenv("BC_MCP_TOOL_LIST_PURCHASE_ORDERS", "List_PurchaseOrders_PAG30066")
    )
    get_po_lines: str = Field(
        default_factory=lambda: os.getenv(
            "BC_MCP_TOOL_GET_PO_LINES",
            "List_PurchaseOrderLinesOfPurchaseOrder_PAG30067",
        )
    )
    list_items: str = Field(default_factory=lambda: os.getenv("BC_MCP_TOOL_LIST_ITEMS", "List_Items_PAG30008"))
    list_purchase_receipts: str = Field(
        default_factory=lambda: os.getenv("BC_MCP_TOOL_LIST_PURCHASE_RECEIPTS", "List_PurchaseReceipts_PAG30064")
    )
    create_purchase_receipt: str = Field(
        default_factory=lambda: os.getenv("BC_MCP_TOOL_CREATE_PURCHASE_RECEIPT", "Create_PurchaseReceipt_PAG30064")
    )
    create_purchase_receipt_line: str = Field(
        default_factory=lambda: os.getenv(
            "BC_MCP_TOOL_CREATE_PURCHASE_RECEIPT_LINE",
            "Create_PurchaseReceiptLine_PAG30065",
        )
    )
    post_purchase_receipt: str = Field(
        default_factory=lambda: os.getenv(
            "BC_MCP_TOOL_POST_PURCHASE_RECEIPT",
            "ReceiveAndInvoice_PurchaseOrders_PAG30066",
        )
    )


class BCMCPSettings(BaseModel):
    """Connection and tool configuration for the Business Central native MCP server."""

    model_config = ConfigDict(extra="forbid")

    server_url: str = Field(
        default_factory=lambda: os.getenv("BC_MCP_SERVER_URL", "https://mcp.businesscentral.dynamics.com")
    )
    tenant_id: str = Field(
        default_factory=lambda: os.getenv("BC_MCP_TENANT_ID", "562029ef-9022-45a6-b255-40cd71ebb2ce")
    )
    environment_name: str = Field(default_factory=lambda: os.getenv("BC_MCP_ENVIRONMENT_NAME", "Production"))
    company: str = Field(default_factory=lambda: os.getenv("BC_MCP_COMPANY", "CRONUS USA, Inc."))
    configuration_name: str = Field(default_factory=lambda: os.getenv("BC_MCP_CONFIGURATION_NAME", "DefaultMCPKiko"))
    scope: str = Field(
        default_factory=lambda: os.getenv(
            "BC_MCP_SCOPE",
            "https://mcp.businesscentral.dynamics.com/.default",
        )
    )
    request_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("BC_MCP_TIMEOUT_SECONDS", "30")),
        gt=0,
    )
    tool_names: BCMCPToolNames = Field(default_factory=BCMCPToolNames)

    @property
    def normalized_server_url(self) -> str:
        """Return the server URL without a trailing slash."""

        return self.server_url.rstrip("/")

    def operation_context(self) -> dict[str, str]:
        """Return the tenant/environment context added to every MCP tool call."""

        return {
            "tenantId": self.tenant_id,
            "environmentName": self.environment_name,
            "company": self.company,
            "configurationName": self.configuration_name,
        }

    def tool_name_for(self, operation: str) -> str:
        """Resolve the MCP tool name for a logical operation."""

        try:
            return getattr(self.tool_names, operation)
        except AttributeError as exc:
            raise KeyError(f"Unknown BC MCP operation: {operation}") from exc


@lru_cache(maxsize=1)
def get_bc_mcp_settings() -> BCMCPSettings:
    """Return the cached Business Central MCP settings."""

    return BCMCPSettings()
