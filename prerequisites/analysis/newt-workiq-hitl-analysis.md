# Newt — WorkIQ Email HITL Feasibility

**Requested by:** Kiko de Angel  
**Date:** 2026-05-03

## Executive summary

**Email-based HITL is feasible**, but **not via `workiq-ask_work_iq` alone**.

The viable paths are:

1. **Custom Outlook Actionable Message** sent as HTML email (via Microsoft Graph or another mail sender) with `Action.Http` callbacks to our backend.
2. **Power Automate email approval flow** as the lowest-effort M365-native option.
3. **Hybrid MVP (recommended)**: email for notification + accept/reject in Outlook + **Modify** handled by a link to a small web form.

### Bottom line
- **WorkIQ itself is mainly the “brain”** (query/reason over M365 data), not the workflow/action runtime.
- **Outlook Actionable Messages** can provide **in-email buttons**.
- **Microsoft Graph `sendMail`** can send the HTML email, but Graph does **not** provide approval semantics by itself.
- **Power Automate** is the fastest path if we want audit trail, reminders, and less custom code.

---

## 1. What I found about WorkIQ

### 1.1 What WorkIQ can do
Using `workiq-ask_work_iq`, I confirmed:
- Outlook/M365 **can** support actionable approval emails.
- Microsoft 365 approval workflows are commonly implemented with **Power Automate Approvals** or **Outlook Actionable Messages**.

### 1.2 What WorkIQ does **not** do by itself
The strongest WorkIQ answer was explicit: WorkIQ is primarily an **intelligence/grounding layer** over Microsoft 365 data, not a standalone workflow or approval engine.

That means WorkIQ is useful to:
- retrieve context,
- summarize discrepancies,
- help draft human-facing content,
- ground decisions in M365 information,

but not to:
- natively orchestrate approval state,
- expose approval buttons by itself,
- receive approval callbacks,
- manage reminders/escalations by itself.

### 1.3 Important nuance: there *is* a Work IQ Mail MCP server in preview
Microsoft Learn documents a **Work IQ Mail** MCP server (preview) with mail operations such as:
- create draft,
- send mail,
- reply,
- update message,
- list sent items,
- search messages.

However:
- that is a **separate MCP server/tool surface**,
- it is **not** the same thing as `workiq-ask_work_iq`,
- and even if available, it still sends mail **through Microsoft Graph Mail API**.

So even with Work IQ Mail, the actionable-button behavior would still depend on **Outlook Actionable Messages**, **registration**, and a **backend callback endpoint**.

**Conclusion:** WorkIQ is helpful context, but **not sufficient alone** for email HITL.

---

## 2. Outlook Actionable Messages — official feasibility

## 2.1 Yes, Outlook supports actionable approval emails
Official Microsoft docs confirm that Outlook supports **Actionable Messages** using **Adaptive Cards** embedded in email.

Key facts:
- actionable email is supported for **individual recipients**,
- recipient must be visible in **To/CC** (not BCC),
- recipient must have **Outlook.com** or **Exchange Online** mailbox,
- admins can disable Actionable Messages tenant-wide.

## 2.2 How they are sent
The card is embedded in an **HTML** email body by placing Adaptive Card JSON inside:

```html
<script type="application/adaptivecard+json">
  { ...card json... }
</script>
```

Important implementation rules:
- email body **must be HTML**,
- for real recipients, `originator` is required,
- `originator` must come from the **Actionable Email Developer Dashboard** registration,
- sender verification/security must be configured.

## 2.3 How actions work
Outlook Actionable Messages use **`Action.Http`**, not Teams-style `Action.Submit`.

Important consequences:
- **`Action.Submit` is not supported** in Outlook Actionable Messages,
- actions call an **internet-accessible HTTP endpoint**,
- the endpoint receives a **JWT bearer token** signed by Microsoft,
- our backend must validate the token and process the request.

## 2.4 How responses are received
The response path is a **webhook-like HTTP POST** to our endpoint.

Official docs specify:
- the service should validate the bearer token in `Authorization`,
- if `Authorization` conflicts with the target platform, Outlook can send the token in `Action-Authorization` instead,
- we can include our own correlation token in the action URL/body,
- Microsoft recommends logging `correlationId`, `Card-Correlation-Id`, and `Action-Request-Id`.

## 2.5 Can the email update itself after click?
Yes.

Outlook supports **refresh cards**:
- backend returns HTTP 200,
- backend includes updated card JSON in the response body,
- backend sets `CARD-UPDATE-IN-BODY: true`.

This lets us replace:
- Accept / Reject / Modify buttons
- with a final status such as **Accepted**, **Rejected**, or **Modification requested**.

---

## 3. Can we support Accept / Reject / Modify?

## 3.1 Accept / Reject
**Yes, strongly feasible.**

This is the native sweet spot for Actionable Messages and also the standard Power Automate approval scenario.

## 3.2 Modify
**Partially feasible inside email, but weaker than Teams.**

Why:
- Outlook email actions are based on `Action.Http`, not `Action.Submit`.
- Microsoft explicitly says refresh cards should **not** be used as multi-step “wizard” flows.
- This makes complex in-card correction UX less natural than Teams.

### Practical options for “Modify”

#### Option A — lightweight in-email modify
Use simple card inputs such as:
- corrected quantity,
- short comment,
- reason code.

Then send them to backend through `Action.Http`.

This works for **small, structured corrections**.

#### Option B — recommended hybrid modify
Use three actions:
- **Accept**
- **Reject**
- **Modify**

Where **Modify** opens a small web form (`Action.OpenUrl`) with:
- discrepancy details,
- editable quantities,
- comments,
- submit + audit logging.

This is safer and more usable for albarán discrepancies than trying to force a mini-editor into the email.

**Recommendation:** for this project, treat **Modify** as a **link to a correction form**, not a full in-email editing experience.

---

## 4. Design for the email-based HITL flow

## 4.1 Recommended architecture

```text
Discrepancy detected
  -> Backend creates approval record
  -> Backend generates Actionable Message card
  -> Email sent via Graph sendMail (or Work IQ Mail if later exposed)
  -> Store manager receives Outlook email
  -> Clicks Accept / Reject / Modify
  -> Outlook posts Action.Http to backend endpoint
  -> Backend validates Microsoft JWT + correlation token
  -> Backend updates state in approval store
  -> Backend returns refresh card / final status
  -> Orchestrator continues workflow
```

## 4.2 Email contents
The email/card should include:
- supplier / store / document id,
- purchase order reference,
- extracted quantity vs expected quantity,
- discrepancy explanation,
- confidence / reason,
- buttons:
  - **Accept**
  - **Reject**
  - **Modify**
- fallback HTML body for non-supporting clients.

## 4.3 Send path
### If we go custom
Use **Microsoft Graph `sendMail`** with:
- HTML body,
- embedded `<script type="application/adaptivecard+json">`,
- `Mail.Send` permission.

### If we go lower-code
Use **Power Automate**:
- either **Approvals**,
- or **Send email with options**,
- and branch on the selected response.

## 4.4 Receive path
Backend endpoint should:
1. accept POST from `Action.Http`,
2. validate Microsoft token,
3. validate service correlation token / request id,
4. ensure idempotency,
5. persist approver identity + timestamp + response,
6. return refresh card or success state.

## 4.5 Timeout handling
### For custom Actionable Message path
There is **no built-in 24h/48h SLA workflow** in Actionable Messages themselves.

So we must implement timers in our orchestration layer:
- **T+24h:** reminder email,
- **T+48h:** escalation email to backup approver / supervisor,
- mark approval record as `pendiente_escalacion` or equivalent.

Best implementation options:
- **Durable Functions** timers,
- **Power Automate** scheduled reminders,
- or another workflow/orchestration engine already approved in this project.

### For Power Automate path
Power Automate is materially better because prior project analysis already notes it as the native path with **built-in reminders/timeouts/escalation** and audit trail.

---

## 5. If WorkIQ is not sufficient, what is the minimum viable alternative?

## 5.1 MVP alternative (best balance)
**Power Automate + Outlook email + small web form for Modify**

Flow:
1. system detects discrepancy,
2. Power Automate sends approval email,
3. approver chooses:
   - Accept,
   - Reject,
   - Modify,
4. if Modify -> open web form,
5. backend records final outcome,
6. reminders/escalations handled by flow timers.

Why this is the best MVP:
- low code,
- native M365 governance,
- easy audit trail,
- no custom Outlook registration complexity if standard approval path is enough,
- handles 24h/48h operational SLA better than pure custom email cards.

## 5.2 Can we use Microsoft Graph API directly?
**Yes.**

But be precise:
- Graph can **send the email**,
- Graph does **not** magically add approval behavior by itself,
- the approval behavior comes from **registered Outlook Actionable Message markup** plus our **HTTP callback endpoint**.

So Graph direct is viable for a custom implementation, but it is **not** the lowest-effort option.

## 5.3 Can we use Power Automate as a bridge?
**Yes — and this is likely the best bridge.**

Power Automate can:
- send approval-style emails,
- wait for response,
- branch logic on outcome,
- send reminders,
- escalate,
- keep an audit record,
- invoke our backend/webhook when decision arrives.

This is the cleanest bridge between a custom backend and the M365 approval channel.

---

## 6. Comparison with the Teams approach

| Feature | Email (WorkIQ / Actionable / Power Automate) | Teams (Bot / Adaptive Card) | Winner |
|---|---|---|---|
| Send notification | **Yes**. Graph/Power Automate can do this easily. WorkIQ alone: **No**. | **Yes** | Tie |
| Accept / reject buttons | **Yes** via Outlook Actionable Messages or Power Automate approvals | **Yes** | Tie |
| Modify quantities | **Partial**. Feasible for simple input, but best as link to web form | **Yes**. Better interactive card UX | Teams |
| Receive response | **Yes** via `Action.Http` callback or Power Automate outcome | **Yes** via bot/webhook submit flow | Tie |
| Timeout / reminders | **Partial** custom; **Strong** with Power Automate | **Yes** | Email with Power Automate; otherwise Teams |
| Audit trail | **Partial** custom; **Strong** with Power Automate approvals | **Yes** | Email with Power Automate; otherwise Tie |

### Practical reading of the table
- **Pure custom email Actionable Message** is better than I expected for accept/reject, but weaker for complex modify UX.
- **Teams** still wins on rich in-card interaction.
- **Email + Power Automate** is probably the best operational fit for a 24h–48h human SLA if Kiko wants email as the main HITL channel.

---

## 7. Final recommendation

## Recommended decision
Adopt **email-based HITL**, but **do not rely on WorkIQ alone**.

### Preferred implementation order
1. **MVP:** Power Automate email approval + backend callback + web form for Modify.
2. **If custom branding/control is needed:** Graph `sendMail` + Outlook Actionable Message + Azure Function / Logic App endpoint.
3. **Use WorkIQ only as support intelligence**, e.g. summarizing discrepancy context or retrieving related M365 information.

### Why this is the best fit
- aligns with Kiko’s shift from Teams to email,
- avoids treating WorkIQ as something it is not,
- gives us accept/reject immediately,
- keeps Modify realistic instead of over-engineering email cards,
- supports reminder/escalation requirements with less custom code.

### Final verdict
**Feasible: YES**  
**Feasible with WorkIQ alone: NO**  
**Best path: Power Automate bridge or custom Actionable Message over Graph**

---

## Sources used

### WorkIQ / M365 responses
- `workiq-ask_work_iq`: Actionable buttons in Outlook are supported via Actionable Messages / Adaptive Cards.
- `workiq-ask_work_iq`: M365 approval workflow via email is best handled by Power Automate Approvals or Outlook Actionable Messages.
- `workiq-ask_work_iq`: WorkIQ is mainly a query/reasoning layer, not the action runtime.

### Official Microsoft documentation
- Outlook Actionable Messages — Get started: `https://learn.microsoft.com/outlook/actionable-messages/get-started`
- Outlook Actionable Messages — Adaptive Card format: `https://learn.microsoft.com/outlook/actionable-messages/adaptive-card`
- Outlook Actionable Messages — Security requirements: `https://learn.microsoft.com/outlook/actionable-messages/security-requirements`
- Microsoft Graph `user: sendMail`: `https://learn.microsoft.com/graph/api/user-sendmail?view=graph-rest-1.0`
- Power Automate — Wait for approval: `https://learn.microsoft.com/power-automate/wait-for-approvals`
- Work IQ Mail reference (preview): `https://learn.microsoft.com/microsoft-agent-365/mcp-server-reference/mail`

### Internal project context
- `prerequisites/analysis/newt-mcp-analysis.md`
- `prerequisites/analysis/ripley-requirements-analysis.md`
