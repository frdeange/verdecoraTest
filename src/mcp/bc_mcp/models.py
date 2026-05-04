from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Vendor(BaseModel):
    """Business Central vendor projection used by the MCP client."""

    model_config = ConfigDict(extra="allow")

    id: str
    number: str | None = None
    displayName: str | None = None
    email: str | None = None
    phoneNumber: str | None = None
    blocked: bool | None = None
    lastModifiedDateTime: datetime | None = None


class PurchaseOrder(BaseModel):
    """Business Central purchase order projection used by the MCP client."""

    model_config = ConfigDict(extra="allow")

    id: str
    number: str | None = None
    vendorId: str | None = None
    vendorNumber: str | None = None
    vendorName: str | None = None
    orderDate: str | None = None
    postingDate: str | None = None
    requestedReceiptDate: str | None = None
    status: str | None = None
    fullyReceived: bool | None = None
    lastModifiedDateTime: datetime | None = None


class PurchaseOrderLine(BaseModel):
    """Business Central purchase order line projection used by the MCP client."""

    model_config = ConfigDict(extra="allow")

    id: str
    documentId: str | None = None
    sequence: int | None = None
    lineType: str | None = None
    lineObjectNumber: str | None = None
    description: str | None = None
    quantity: float | None = None
    directUnitCost: float | None = None
    receivedQuantity: float | None = None
    expectedReceiptDate: str | None = None


class Item(BaseModel):
    """Business Central item projection used by the MCP client."""

    model_config = ConfigDict(extra="allow")

    id: str
    number: str | None = None
    displayName: str | None = None
    itemCategoryCode: str | None = None
    blocked: bool | None = None
    inventory: float | None = None
    unitPrice: float | None = None
    unitCost: float | None = None
    baseUnitOfMeasureCode: str | None = None
    lastModifiedDateTime: datetime | None = None


class PurchaseReceipt(BaseModel):
    """Business Central posted purchase receipt projection used by the MCP client."""

    model_config = ConfigDict(extra="allow")

    id: str
    number: str | None = None
    vendorNumber: str | None = None
    vendorName: str | None = None
    postingDate: str | None = None
    invoiceDate: str | None = None
    dueDate: str | None = None
    orderNumber: str | None = None
    lastModifiedDateTime: datetime | None = None
