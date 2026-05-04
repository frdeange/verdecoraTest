# ACS Email HITL PoC

## What was tested

This proof of concept validates the proposed **ACS Email + web form** approval path for albarán discrepancies:

1. A Python sender composes a branded HTML HITL email.
2. The email contains **Accept**, **Modify**, and **Reject** buttons that open a web surface rather than relying on Outlook Actionable Messages.
3. A FastAPI stub captures the user decision so Sprint 3 can later replace the in-memory store with Cosmos DB + Service Bus events.
4. Reminder (24h) and escalation (48h) templates prove that timer-driven follow-ups can reuse the same link model.

## SDK package and API

- **Package:** `azure-communication-email`
- **Latest package version researched:** `1.1.0`
- **Primary client:** `azure.communication.email.EmailClient`
- **Send API used in this PoC:** `EmailClient.begin_send(message)`
- **Authentication patterns:** connection string or `DefaultAzureCredential()`

The Azure MCP `azure-communication` surface also confirms a first-party `communication_email_send` command with support for HTML bodies, CC/BCC, reply-to, and sender display name.

## Files created

- `src/poc/acs_email_poc/email_templates.py`
- `src/poc/acs_email_poc/send_email.py`
- `src/poc/acs_email_poc/reminder_template.py`
- `src/poc/acs_email_poc/escalation_template.py`
- `src/poc/acs_email_poc/hitl_webform_stub.py`

## Rendered HTML preview

### Initial HITL email

```html
<div style="background:linear-gradient(90deg,#14532d,#166534);color:#ffffff;">
  <h1>Albarán discrepancy awaiting decision</h1>
</div>
<div>
  <strong>Supplier:</strong> Viveros Norte<br />
  <strong>PO reference:</strong> PO-2026-00421
</div>
<table>
  <tr>
    <th>Product</th><th>Description</th><th>Albarán qty</th><th>PO qty</th><th>Difference</th><th>Impact</th>
  </tr>
  <tr>
    <td>SKU-PLANT-001</td><td>Monstera deliciosa 17cm</td><td>24</td><td>20</td><td>4</td><td>Inventory overage</td>
  </tr>
</table>
<a href="https://hitl-webform.example.com/api/hitl/HITL-001/accept?token=demo-token">Accept</a>
<a href="https://hitl-webform.example.com/api/hitl/HITL-001/modify?token=demo-token">Modify</a>
<a href="https://hitl-webform.example.com/api/hitl/HITL-001/reject?token=demo-token">Reject</a>
```

### Reminder email (24h)

```html
<div style="background:#78350f;color:#ffffff;">
  <h1>Decision still pending for albarán A-2026-00045</h1>
</div>
```

### Escalation email (48h)

```html
<div style="background:#991b1b;color:#ffffff;">
  <h1>Urgent approval needed for albarán A-2026-00045</h1>
</div>
```

## How to run the PoC locally

### Send the email

```bash
pip install azure-communication-email azure-identity
python -c "from datetime import date; from src.poc.acs_email_poc.email_templates import DiscrepancyLine, HitlEmailContext; from src.poc.acs_email_poc.send_email import ACSMessageConfig, send_hitl_email; ctx = HitlEmailContext(albaran_id='HITL-001', albaran_number='A-2026-00045', supplier_name='Viveros Norte', delivery_date=date.today(), po_reference='PO-2026-00421', pdf_url='https://storage.example.com/albaran.pdf?<sas>', token='demo-token', discrepancy_lines=[DiscrepancyLine(product='SKU-PLANT-001', description='Monstera deliciosa 17cm', albaran_qty=24, po_qty=20, impact='Inventory overage')]); cfg = ACSMessageConfig(endpoint='https://example.communication.azure.com', sender_address='noreply@example.com', recipient_address='manager@example.com'); print(send_hitl_email(ctx, cfg))"
```

### Run the web form stub

```bash
pip install fastapi uvicorn python-multipart
uvicorn src.poc.acs_email_poc.hitl_webform_stub:app --reload
```

## Integration notes for Sprint 3

1. Replace the hard-coded `https://hitl-webform.example.com` host with the real Container App ingress URL or front-door hostname.
2. Generate short-lived, action-bound signed tokens and validate them server-side before any state transition.
3. Persist the pending HITL request and final response in Cosmos DB.
4. Emit `hitl.response.*` events to Service Bus so scheduled reminder/escalation messages can be cancelled.
5. Add Entra-authenticated approver identity capture, replay protection, audit logs, and CSRF protection on the web form.
6. Attach the stored PDF URL from Blob Storage and include plain-text fallback links for restrictive mail clients.
