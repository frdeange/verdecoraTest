# BC MCP / Inventory Analysis — Burke

**Author:** Burke (BC/Dynamics Specialist)  
**Date:** 2026-05-03  
**Scope:** Validate the PRD's Business Central assumptions for Purchase Orders, Warehouse Receipts, and Item Journals.

---

## 1. BC MCP Server Configuration Guide

### What "MCP Configurations" are in Business Central

In Business Central, **MCP Configurations** are named configuration records on the **Model Context Protocol (MCP) Server Configurations** page that define:
- which **API page objects** are exposed to agents,
- which operations are allowed per object (**Read / Create / Modify / Delete / Bound Actions**), and
- whether tools are discovered explicitly or dynamically at runtime.

They are reusable, can be **activated/deactivated**, and can be **exported/imported as JSON**.

### How entity exposure works

Business Central's native MCP server exposes **API pages**, not arbitrary tables.

Key rules from Microsoft Learn:
- By default, the MCP server gives **read-only access to all exposed API pages**.
- To expose a specific entity intentionally, add its **top-level API page object** to **Available Tools** in an MCP configuration.
- You can also use **Add All Standard APIs as Tools**.
- **ListPart** and **CardPart** API pages are **not** supported as MCP tools; only **top-level API pages** can be added.
- **Dynamic Tool Mode** helps when the client tool-count limit is a concern.
- **Discover Additional Objects** + **Dynamic Tool Mode** allows agents to access **all API pages in the environment read-only**, even when not explicitly added.
- **Unblock Edit Tools** must be turned on before **Allow Create / Allow Modify / Allow Delete / Allow Bound Actions** actually take effect.

### Practical recommendation

Use **two MCP configurations**, not one:

1. **BC-Read-Validation**
   - `Unblock Edit Tools = Off`
   - Read-only exposure for: Purchase Orders, Purchase Order Lines, Vendors, Items, and Posted Purchase Receipts.

2. **BC-Inventory-Execution**
   - `Unblock Edit Tools = On`
   - Explicitly expose only the write-capable APIs/custom APIs actually needed.
   - Keep `Allow Delete = false` everywhere.

This is safer than relying on a single broad configuration.

---

## 2. Entity Availability Matrix

| PRD entity | Native standard BC API page? | MCP-ready natively? | Evidence / notes | Recommendation |
|---|---|---:|---|---|
| Purchase Orders | Yes | Yes | Standard API page **30066 `APIV2 - Purchase Orders`** (`EntitySetName = 'purchaseOrders'`). | Safe to use natively via MCP. |
| Purchase Lines | Yes | Yes | Standard API page **30067 `APIV2 - Purchase Order Lines`** (`EntitySetName = 'purchaseOrderLines'`). | Safe to use natively via MCP. |
| Vendors | Yes | Yes | Standard API page **30010 `APIV2 - Vendors`** (`EntitySetName = 'vendors'`). | Safe to use natively via MCP. |
| Items | Yes | Yes | Standard API page **30008 `APIV2 - Items`** (`EntitySetName = 'items'`). | Safe to use natively via MCP. |
| Warehouse Receipts | No standard API page found | No | I found Microsoft docs for the **Warehouse Receipt** process, but **no standard APIV2 top-level warehouse receipt API page** in Microsoft's ALAppExtensions standard API set. | **Custom API page/bound action likely required** if this must be driven through MCP. |
| Item Journal Lines | No item-specific standard API page found | No | Standard APIs expose **Journals / JournalLines**, but these are **General Journal** objects (`SourceTable = Gen. Journal Batch / Gen. Journal Line`), **not Item Journal Line**. | **Custom API page/bound action required** if the design truly depends on Item Journal Lines. |
| Posted Purchase Receipts | Yes | Yes (read-only) | Standard API page **30064 `APIV2 - Purchase Receipts`** and **30065 `APIV2 - Purch Receipt Lines`**, both explicitly **read-only**. | Use for audit/confirmation after receiving. |

### Important detail: Purchase Order Lines already expose receiving fields

The standard **purchase order lines** API includes:
- `receivedQuantity` (`Quantity Received`)
- `invoiceQuantity` (`Qty. to Invoice`)
- `receiveQuantity` (`Qty. to Receive`)

So the PRD assumption that `Qty. to Receive` maps to Purchase Lines is **correct**.

### Bottom line

The **read-side** of the PRD is mostly valid natively.

The **write-side** is **not fully valid natively**:
- **Warehouse Receipts** are not exposed through a standard top-level APIV2 page.
- **Item Journal Lines** are not exposed natively as item-journal APIs; the closest standard API is for **General Journal Lines**, which is not the same thing.

---

## 3. Correct Inventory Flow (BC's way vs PRD's assumptions)

### What BC supports natively

Business Central supports multiple inbound flows depending on **Location** setup:

- **Method A** — post receipt directly from the order line (no dedicated warehouse activity)
- **Method B** — inventory put-away
- **Method C** — warehouse receipt
- **Method D** — warehouse receipt + warehouse put-away

### Where the PRD is correct

The PRD is correct that:
- purchase lines can carry `Qty. to Receive`, and
- warehouse documents update source document quantities.

### Where the PRD is too rigid

The PRD assumes **Agent 3 should create Warehouse Receipts** and then update Purchase Lines. That is **not always BC's correct flow**.

#### If the location does **not** require warehouse receipts
BC's normal process is:
1. update **Qty. to Receive** on the purchase order line,
2. post the purchase order with **Receive**, and
3. let BC create a **Posted Purchase Receipt**.

That is the cleanest standard purchase receiving flow.

#### If the location **does** require warehouse receipts
Then BC's correct process is:
1. release the source document,
2. create/get source lines into **Warehouse Receipt**,
3. post the warehouse receipt,
4. optionally continue with warehouse put-away if the location requires it.

So the decision is **location-driven**, not universally document-driven.

### Should we use Posted Purchase Receipt instead?

**Yes, as the confirmation/audit artifact.**

The posted receipt is the durable proof that goods were received. It already exists as a **native read-only API** (`purchaseReceipts` / `purchaseReceiptLines`) and is a better downstream validation target than an open warehouse document.

### What about the standard purchaseOrder bound action?

The standard `purchaseOrder` API exposes a bound action:
- **`receiveAndInvoice`**

But I did **not** find a native standard **receive-only** bound action in the standard purchase-order API. That matters because the warehouse/receiving workflow in the PRD appears to need **receipt without immediate invoicing**.

### Is Item Journal Line the right entity for inventory movement?

**Only for inventory adjustments or movements that are not normal PO receiving.**

Item journals are appropriate for scenarios like:
- positive/negative adjustments,
- reclassifications,
- corrections outside the purchase receipt flow.

They are **not** the normal first choice for receiving goods against a purchase order.

### Recommended architectural interpretation

1. **Use Purchase Order + Purchase Order Line APIs for validation and receipt preparation.**
2. **Use direct PO receipt flow when the location does not require warehouse documents.**
3. **Use Warehouse Receipt only for warehouse-enabled locations that require it.**
4. Treat **Posted Purchase Receipt** as the main downstream evidence of success.
5. Do **not** make Item Journal Line the default receiving mechanism.

---

## 4. CRONUS Test Data Assessment

### What we can say confidently

- **CRONUS** is the standard Business Central demonstration company used in Microsoft walkthroughs.
- It is appropriate for **learning, demos, and baseline functional testing**.
- Microsoft explicitly notes that **some walkthroughs require sample data not available in the default demonstration company**.
- Sandbox environments are the correct place to test safely.

### What I could not verify in this session

I could **not** enumerate the exact live **Purchase Orders currently present in `CRONUS USA Inc.`** because this session had documentation/search access, but **no live Business Central data-access tool** connected to the tenant/company.

So the question **"what purchase orders exist right now in that environment?"** remains open until someone queries the environment directly through BC or a working BC MCP/API connection.

### Is the demo data sufficient?

**Sufficient for baseline testing:**
- item/vendor matching,
- purchase order line comparisons,
- partial-vs-full receipt logic,
- posted receipt verification,
- basic warehouse vs non-warehouse branching.

**Not sufficient by itself for full project confidence:**
- edge-case warehouse setups,
- over-receipt policy/tolerance scenarios,
- company-specific customizations,
- exact production-like approval/posting rules,
- item-journal-specific integration behavior.

### Recommended test scenarios

1. **PO validation only**
   - Match vendor, item, quantity, unit cost against an existing purchase order.

2. **Partial receipt**
   - Set `Qty. to Receive` below ordered quantity and verify `Quantity Received` updates correctly.

3. **Full receipt**
   - Receive all ordered lines and verify a **Posted Purchase Receipt** is created.

4. **Warehouse-required location**
   - Use a location with **Require Receive** and verify the flow must go through **Warehouse Receipt**.

5. **Mismatch scenario**
   - Wrong vendor / wrong item / wrong quantity outside tolerance.

6. **Over-receipt**
   - Validate behavior where actual receipt exceeds ordered quantity.

7. **Adjustment scenario**
   - Only if item journals remain in scope: test a positive/negative adjustment using a **custom item journal API**, not the standard journal API.

### Environment recommendation

Do **not** use the production CRONUS environment for write testing. Use a **sandbox cloned from the target configuration** whenever write operations are involved.

---

## 5. Permission Model Design

### How to enforce "NO DELETE"

At the MCP layer:
- Keep **`Allow Delete = false`** for every tool.
- For the read-only config, set **`Unblock Edit Tools = Off`** so all write permissions are forced off.

### How to split read-only vs create/update

#### Config A — Read/Validation
- Purchase Orders — `Allow Read = true`
- Purchase Order Lines — `Allow Read = true`
- Vendors — `Allow Read = true`
- Items — `Allow Read = true`
- Purchase Receipts / Receipt Lines — `Allow Read = true`
- `Unblock Edit Tools = Off`

#### Config B — Inventory/Execution
- Purchase Order Lines — `Allow Read = true`, `Allow Modify = true` (only if we intentionally let the agent set `Qty. to Receive`)
- Purchase Orders — `Allow Read = true`, optionally `Allow Bound Actions = true` **only** if `receiveAndInvoice` is truly acceptable
- Custom Warehouse Receipt API — `Allow Read/Create/Modify` as required
- Custom Item Journal API — `Allow Read/Create/Modify` as required
- `Allow Delete = false` everywhere
- `Unblock Edit Tools = On`

### BC permission sets needed

#### Admin/configuration
- The person configuring MCP needs at least **`MCP - ADMIN`** (or equivalent).

#### Runtime/integration
Use **custom least-privilege permission sets**, not broad admin sets.

Recommended shape:

1. **BC_MCP_PO_READ**
   - Read access for Items, Vendors, Purchase Orders, Purchase Order Lines, Posted Purchase Receipts.

2. **BC_MCP_RECEIPT_EXEC**
   - Add only the modify/execute permissions needed for the chosen receipt flow.
   - If the flow is warehouse-based, include the warehouse receipt objects and posting requirements.
   - If the flow is PO-posting-based, include the specific posting/bound-action permissions needed.

3. **BC_MCP_ITEMJNL_EXEC** *(only if item journals stay in scope)*
   - Permissions for custom item-journal API objects plus the related posting logic.

### Important BC permission design note

System permission sets in Business Central online are not meant to be edited directly. The safe pattern is:
- copy/create **user-defined permission sets**,
- keep them narrowly scoped,
- assign them to the integration user (or security group),
- verify with **Effective Permissions**.

---

## 6. Questions for Kiko

1. **Are the target receiving locations configured with `Require Receive` and/or `Require Put-away`?**  
   This decides whether Warehouse Receipt is required or whether direct PO receipt is the correct flow.

2. **Do we need receipt-only, or is `receiveAndInvoice` acceptable?**  
   Native standard purchase-order API exposes `receiveAndInvoice`, but not a standard receive-only bound action.

3. **Are custom AL APIs / bound actions allowed?**  
   If yes, we can close the gaps for **Warehouse Receipt** and **Item Journal Line** cleanly.

4. **Should Item Journal remain in scope at all for PO-linked receiving?**  
   My recommendation is **no** unless we are explicitly handling adjustments/corrections.

5. **Can we use a sandbox instead of production CRONUS for all write-path testing?**  
   This is strongly recommended.

6. **Do you want the integration to validate against open documents only, or also check posted purchase receipts?**  
   Posted receipts are the better downstream truth for "receipt completed".

---

## Source Highlights

- Microsoft Learn — **Configure Business Central MCP Server**
- Microsoft Learn — **Model Context Protocol (MCP) in Business Central overview**
- Microsoft Learn — **purchaseOrder resource type**
- Microsoft ALAppExtensions — standard APIV2 pages (`Items`, `Vendors`, `Purchase Orders`, `Purchase Order Lines`, `Purchase Receipts`, `Purch Receipt Lines`, `Journals`, `JournalLines`)
- Microsoft Learn — **Receive items** / **Inbound warehouse flow**
- Microsoft Learn — **Business Process Walkthroughs**
- Microsoft Learn — **Sandbox Environments in Business Central**
- Microsoft Learn — **Entitlements and permission sets overview** / **Permission set object**
