"""ACS Email MCP server package."""

from .models import DeliveryStatus, EmailResult
from .server import check_delivery_status, mcp, send_email, send_hitl_notification

__all__ = [
    "DeliveryStatus",
    "EmailResult",
    "check_delivery_status",
    "mcp",
    "send_email",
    "send_hitl_notification",
]
