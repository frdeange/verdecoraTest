# Newt — ACS Email HITL Evaluation

## Executive summary
**ACS Email is a viable HITL channel and is a better fit than Power Automate for Kiko's stated preference of full Python control and no Power Automate dependency.**

However, it is **not a fully private, zero-custom workflow solution**. The strongest shape is:
- ACS Email for outbound rich HTML notification,
- standard HTML action buttons that link to our Container App web form,
- backend state transition in Cosmos DB,
- orchestrator/timer logic outside email for reminders, timeout, and escalation.

**Verdict:** viable and probably preferable **if** we accept custom workflow/orchestration work and a publicly reachable approval edge. If we need native approval lifecycle, reminders, and minimal custom code, Power Automate still wins operationally.

---

## 1. ACS Email MCP findings

The available Azure Communication Services MCP tool exposes a `communication_email_send` command.

### 1.1 Supported send parameters
The MCP command supports:
- `endpoint`
- `from`
- `sender-name`
- `to`
- `cc`
- `bcc`
- `subject`
- `message`
- `is-html`
- `reply-to`
- auth options: `Credential`, `Key`, `ConnectionString`

### 1.2 HTML support
**Yes.** The MCP command explicitly supports HTML bodies via `is-html: true`.

### 1.3 Practical implication
At MCP level, ACS Email is already enough to prove that we can:
- send branded discrepancy emails,
- send to one or more recipients,
- use HTML tables/buttons,
- preserve reply-to / CC patterns if needed.

---

## 2. ACS Email product research

## 2.1 Python SDK
The Python SDK is **`azure-communication-email`** and uses `EmailClient`.

Typical auth patterns:
- `EmailClient(endpoint, DefaultAzureCredential())`
- `EmailClient(endpoint, AzureKeyCredential(key))`

Typical send pattern:

```python
from azure.communication.email import EmailClient
from azure.identity import DefaultAzureCredential

client = EmailClient(
    "https://<resource-name>.communication.azure.com",
    DefaultAzureCredential(),
)

message = {
    "content": {
        "subject": "Discrepancia detectada en albarán A-12345",
        "plainText": "Se ha detectado una discrepancia. Revísela en el portal.",
        "html": "<html><body><h1>Discrepancia detectada</h1><p>...</p></body></html>",
    },
    "recipients": {
        "to": [
            {"address": "responsable.tienda@contoso.com", "displayName": "Responsable tienda"}
        ]
    },
    "senderAddress": "noreply@alerts.contoso.com",
}

poller = client.begin_send(message)
result = poller.result()
```

## 2.2 HTML email support
**Yes.** Official samples show the `content.html` field and `begin_send(...)` for HTML emails. ACS also supports:
- CC / BCC,
- reply-to,
- attachments,
- inline attachments.

## 2.3 Custom sender domains
**Yes.** ACS Email supports:
- Azure-managed sender domains (`*.azurecomm.net`), and
- **custom verified domains**.

For custom domains, Microsoft docs require:
- domain ownership TXT verification,
- SPF TXT record,
- DKIM CNAME records,
- then connecting the verified domain to the Communication Services resource.

This is compatible with using something like:
- `noreply@alerts.verdecora.es`
- `albaranes@ops.verdecora.es`

## 2.4 Pricing
Official Microsoft Learn pricing page states illustrative pay-as-you-go rates of:
- **$0.00025 per email**
- **$0.00012 per MB transferred**

Interpretation for this project:
- 750 discrepancy emails/day would still be inexpensive at the email-service layer.
- The real cost driver is more likely the surrounding app/orchestration pieces than the outbound email itself.

## 2.5 Tracking and events
ACS Email provides:
- send status polling (`Running`, `Succeeded`, `Failed`),
- Event Grid events for delivery reports,
- Event Grid engagement tracking for **open** and **click** events.

Useful event types found in docs:
- `Microsoft.Communication.EmailDeliveryReportReceived`
- `Microsoft.Communication.EmailEngagementTrackingReportReceived`

This is useful for observability, but it does **not** replace the business workflow state change produced by our own web form.

## 2.6 Private networking posture
This is the trickiest part.

What I found:
- ACS has a **Network Security Perimeter (NSP)** integration path for Email,
- but the documented feature is **preview**,
- and the approval link clicked by a human still needs to reach some HTTP endpoint.

So the correct conclusion is **partial compatibility**, not a clean "all-private" story:
- ACS resource access can be tightened,
- backend services can remain in private Azure networking,
- **but the human-facing approval surface cannot be purely private unless users are on VPN/internal network**.

For store managers opening email on regular devices, expect to publish a controlled external edge:
- Front Door / App Gateway / APIM / public ingress,
- strong auth,
- signed short-lived tokens,
- least-privilege callback design.

---

## 3. Proposed HITL flow with ACS Email

```text
Agent 2 detects discrepancy
-> builds discrepancy payload
-> stores pending HITL record in Cosmos DB
-> uses ACS Email SDK to send HTML email
-> email contains 3 buttons linking to web endpoints/forms
-> manager clicks Accept / Modify / Reject
-> Container App endpoint validates token + identity
-> backend updates Cosmos DB HITL state
-> backend emits event / calls orchestrator
-> Agent 3 proceeds for accepted/modified cases
```

## 3.1 Email contents
Recommended HTML content:
- albarán number
- supplier
- store
- date
- discrepancy summary
- table of affected lines:
  - product
  - description
  - albarán qty
  - PO qty
  - difference
- action buttons
- expiry / SLA notice
- fallback plain link

## 3.2 Action buttons
The buttons should be standard HTML links styled as buttons, for example:
- `Accept` -> `https://<host>/api/hitl/{albaran_id}/accept?token=...`
- `Modify` -> `https://<host>/hitl/{albaran_id}/modify?token=...`
- `Reject` -> `https://<host>/api/hitl/{albaran_id}/reject?token=...`

Important: this is **not** Outlook Actionable Message behavior. The email click simply opens our web surface.

That is actually a benefit here:
- no Outlook Actionable Message registration,
- no dependency on Outlook-specific client support,
- no tenant feature dependency,
- uniform behavior across mail clients.

## 3.3 Response handling design
Recommended backend pattern:
1. Create a HITL record in Cosmos DB with status `pending_human_review`.
2. Generate a signed, short-lived token bound to:
   - hitl request id,
   - albarán id,
   - intended recipient,
   - allowed action,
   - expiry.
3. On click:
   - authenticate user with Entra ID if feasible,
   - validate token,
   - ensure request still pending,
   - record action, actor, timestamp, optional comment.
4. For `Modify`, open a web form with editable quantities and server-side validation.
5. After completion:
   - update Cosmos DB,
   - emit event / resume orchestrator,
   - notify downstream Agent 3.

## 3.4 Best place for timers and reminders
**Do not put timers in email.**

Implement reminders/escalation in the orchestrator layer instead, e.g.:
- Durable Functions,
- Service Bus + orchestrator,
- or equivalent state machine/timer component.

That aligns with earlier analysis that email itself is only the notification surface.

---

## 4. Comparison with previous options

| Feature | ACS Email + Web Form | Power Automate | Actionable Messages |
|---|---|---|---|
| Full Python control | **Yes** | **No** | **Partial** |
| HTML email | **Yes** | **Yes** | **Yes** |
| Action buttons | **Yes, via HTML links to our app** | **Yes, native approval UX** | **Yes, native in-email actions** |
| Private VNet compatible | **Partial** | **No** | **No / weak for strict private-only** |
| No external dependencies | **Yes** (no PA/M365 approval runtime) | **No** | **No** (registration + Outlook dependency) |
| Timeouts/reminders | **No native support** | **Yes, native** | **No native support** |
| Cost | **Low usage cost** (`$0.00025/email` + `$0.00012/MB`) | **PA license / flow cost** | **No separate action fee, but M365/Graph dependency remains** |

## Practical reading of the table
- **ACS Email wins on engineering control and low direct cost.**
- **Power Automate wins on workflow features** (timeouts, reminders, escalation, built-in approval semantics).
- **Actionable Messages wins on in-email UX**, but adds Outlook-specific constraints and registration overhead.

---

## 5. Viability verdict

## 5.1 Is ACS Email better for this project?
**Probably yes, for Kiko's preference set.**

Why it is attractive here:
1. **Full Python control** end-to-end.
2. **No Power Automate dependency**.
3. **Simple mental model**: email is notification, web app is action surface.
4. **Private-network-friendly backend posture** is easier than M365 callback-centric approaches, even if not perfectly private end-to-end.
5. **Cheap** at projected scale.
6. **Modify** becomes straightforward because a normal web form is the primary UX, not an email card hack.

## 5.2 Main gotchas
1. **Human click path must be reachable.** If approvers are not on VPN/internal network, the approval page needs a secure external entry point.
2. **No native reminders/timeouts/escalations.** We must build them in orchestration.
3. **Email client rendering varies.** Keep HTML conservative and include plain links.
4. **Security is on us.** Signed tokens, auth, replay protection, expiration, and audit logging are mandatory.
5. **Deliverability/domain setup required.** Custom domain verification plus SPF/DKIM must be done correctly.
6. **ACS network hardening story is not fully mature.** NSP exists, but documented Email setup is preview.
7. **Clicks are not approvals by themselves.** The real approval event should only occur after server-side validation and persisted state transition.

## 5.3 Recommended implementation decision
If the team accepts modest custom workflow code, adopt:
- **ACS Email + Container App web form + orchestrator timers**

Recommended fallback if operational simplicity is prioritized over engineering control:
- **Power Automate approval email + backend callback + web form for Modify**

## Final verdict
**Feasible: YES**  
**Better than Power Automate for Kiko's stated preference: YES**  
**Gotcha-free replacement: NO**

ACS Email is the best fit if we deliberately treat email as the notification channel and the web app/orchestrator as the real HITL engine.

---

## Sources
- Azure Communication MCP `communication_email_send` tool surface (`is-html`, sender/recipient parameters, auth options)
- Microsoft Learn: *Send an email using Azure Communication Services (Python)*
- Microsoft Learn: *Email pricing in Azure Communication Services*
- Microsoft Learn: *Add custom verified domains*
- Microsoft Learn: *Azure Communication Services - Email events*
- Microsoft Learn: *Create a Network Security Perimeter* (ACS Email preview path)
- `web_search`: ACS Email Python SDK / pricing / private-networking cross-check (2026)
- Prior repo analysis: `prerequisites/analysis/newt-workiq-hitl-analysis.md`
