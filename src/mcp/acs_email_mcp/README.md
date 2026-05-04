# ACS Email MCP

FastMCP wrapper around Azure Communication Services Email using `DefaultAzureCredential`.

## Environment
- `ACS_ENDPOINT`
- `ACS_SENDER_ADDRESS`

## Tools
- `send_email(to, subject, body_html, reply_to)`
- `send_hitl_notification(notification)`
- `check_delivery_status(message_id)`
