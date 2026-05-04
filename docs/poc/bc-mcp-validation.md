# BC MCP validation against CRONUS

## Scope
- **Issue:** #2
- **Environment:** Business Central Online / Production
- **Company:** `CRONUS USA, Inc.`
- **MCP configuration:** `DefaultMCPKiko`
- **Validation mode:** Read-only MCP validation against live demo data

## Executive summary
Native BC MCP covers the Sprint 1 read-side well: purchase orders, purchase order lines, vendors, items, and posted purchase receipts are all discoverable and readable from CRONUS. Standard write-capable actions also surface for purchase orders, purchase order lines, vendors, and items, but posted purchase receipts remain read-only and no native warehouse-receipt or item-journal-line action was surfaced in this validation.

## 1. Action inventory discovered with `bc_actions_search`

### Core actions we can use directly
| Entity | MCP actions found |
|---|---|
| Purchase Order | `List_PurchaseOrders_PAG30066`, `Create_PurchaseOrder_PAG30066`, `Modify_PurchaseOrder_PAG30066`, `ReceiveAndInvoice_PurchaseOrders_PAG30066` |
| Purchase Order Line | `List_PurchaseOrderLines_PAG30067`, `Create_PurchaseOrderLine_PAG30067`, `List_PurchaseOrderLinesOfPurchaseOrder_PAG30067`, `Create_PurchaseOrderLinesOfPurchaseOrder_PAG30067` |
| Vendor | `List_Vendors_PAG30010`, `Create_Vendor_PAG30010` |
| Item | `List_Items_PAG30008`, `Create_Item_PAG30008`, `Modify_Item_PAG30008` |
| Posted Purchase Receipt | `List_PurchaseReceipts_PAG30064`, `List_PurchaseReceiptLines_PAG30065`, `List_PurchaseReceiptLinesOfPurchaseReceipt_PAG30065` |

### Additional related actions surfaced
- **Legacy/alternate vendor pages:** `List_Vendors_PAG20010`, `List_Vendors_PAG30308`, `List_Vendors_PAG36959`
- **Legacy/alternate item page:** `List_Items_PAG20008`
- **Inventory-related read page:** `List_ItemLedgerEntries_PAG30069`
- **Related master-data pages:** `List_ItemVariants_PAG20052`, `List_ItemVariantsOfItem_PAG20052`, `List_ItemVariants_PAG30052`, `List_ItemVariantsOfItem_PAG30052`, `List_InventoryPostingGroups_PAG30096`, `List_InventoryPostingGroupOfItem_PAG30096`, `List_Locations_PAG30076`, `List_LocationOfPurchaseOrderLine_PAG30076`, `List_LocationOfPurchaseInvoiceLine_PAG30076`, `List_LocationOfPurchaseCreditMemoLine_PAG30076`, `List_LocationOfSalesInvoiceLine_PAG30076`, `List_LocationOfSalesOrderLine_PAG30076`, `List_LocationOfSalesQuoteLine_PAG30076`, `List_LocationOfSalesCreditMemoLine_PAG30076`
- **Purchase-adjacent pages surfaced by semantic search:** `List_PurchaseInvoices_PAG20042`, `List_PurchaseInvoiceLines_PAG30047`, `List_PurchaseInvoiceLinesOfPurchaseInvoice_PAG30047`, `List_PostedPurchaseInvoices_PAG9971`, `List_SustainabilityPurchaseLines_PAG6336`, `List_VendorPayments_PAG30060`, `List_VendorPaymentsOfVendorPaymentJournal_PAG30060`, `List_VendorPaymentJournals_PAG30061`, `List_VendorContracts_PAG8023`, `List_VendorContractLines_PAG8047`, `List_VendorContractLinesOfVendorContract_PAG8047`, `List_VendorContractDeferrals_PAG8048`, `List_VendorContractDeferralsOfVendorContractLines_PAG8048`
- **Noise surfaced by semantic search:** `List_SalesOrders_PAG20028`, `List_SalesOrders_PAG30028`, `List_SalesOrderLines_PAG30044`, `List_SalesOrderLinesOfSalesOrder_PAG30044`, `List_IntercompanyInboxTransactions_PAG30411`, `List_HandledIntercompanyInboxTransactions_PAG30400`, `List_IntercompanyIncomingNotification_PAG30415`, `List_BufferIntercompanyInboxTransactions_PAG30423`, `List_BufferIntercompanyInboxTransactionsOfIntercompanyOutgoingNotification_PAG30423`, `List_BufferIntercompanyInboxPurchaseHeaders_PAG30420`, `List_BufferIntercompanyInboxPurchaseHeadersOfIntercompanyOutgoingNotification_PAG30420`, `List_BufferIntercompanyInboxPurchaseLines_PAG30419`, `List_BufferIntercompanyInboxPurchaseLinesOfIntercompanyOutgoingNotification_PAG30419`, `List_Attachments_PAG20039`, `List_AttachmentsOfJournalLine_PAG20039`, `List_BufferIntercompanyCommentLines_PAG30416`, `List_BufferIntercompanyCommentLinesOfIntercompanyOutgoingNotification_PAG30416`, `List_IntercompanySetup_PAG30414`, `List_EDocumentFileContent_PAG6119`, `List_EDocumentFileContentOfEDocumentServiceStatus_PAG6119`, `List_GeneralLedgerEntryAttachments_PAG20040`, `List_IntercompanyDimensions_PAG30402`, `List_Features_PAG30092`, `List_CreateQualityInspections_PAG20415`, `List_EDocuments_PAG6112`, `List_PostedESGReportLines_PAG6334`, `List_RetainedEarningsStatement_PAG20029`, `List_RetainedEarningsStatements_PAG30029`, `List_PdfDocument_PAG30056`, `List_PdfDocumentOfSalesInvoice_PAG30056`, `List_PdfDocumentOfSalesOrder_PAG30056`, `List_PdfDocumentOfSalesQuote_PAG30056`, `List_PdfDocumentOfSalesCreditMemo_PAG30056`, `List_PdfDocumentOfPurchaseInvoice_PAG30056`, `List_PdfDocumentOfProject_PAG30056`

### Search quality notes
- Semantic discovery works, but broad prompts such as **inventory** and **receipt** return a noisy mix of relevant APIs, legacy pages, and unrelated intercompany/document pages.
- For Sprint 1, the safest native targets are the standard APIV2-style pages with `PAG300xx` identifiers.

## 2. Schema findings from `bc_actions_describe`

### Purchase orders (`PAG30066`)
| Action | Required params | Key request fields / behavior |
|---|---|---|
| `List_PurchaseOrders_PAG30066` | none | Supports `filter`, `orderby`, `select`, `top`, `skip`, `resultFormat`. Key fields include `id`, `number`, `orderDate`, `postingDate`, `vendorId`, `vendorNumber`, `vendorName`, `requestedReceiptDate`, `fullyReceived`, `status`, totals, addresses, dimensions, `lastModifiedDateTime`. |
| `Create_PurchaseOrder_PAG30066` | none | Writable fields include vendor references, dates, ship-to/buy-from/pay-to addresses, dimensions, currency, payment terms, purchaser, requested receipt date, discount amount, `fullyReceived`. |
| `Modify_PurchaseOrder_PAG30066` | `If-Match`, `id` | Same editable fields as create; requires optimistic concurrency via `@odata.etag`. |
| `ReceiveAndInvoice_PurchaseOrders_PAG30066` | `id` | Bound action exists, but only exposes `id` (+ optional `select`). No native receive-only action surfaced. |

### Purchase order lines (`PAG30067`)
| Action | Required params | Key request fields / behavior |
|---|---|---|
| `List_PurchaseOrderLines_PAG30067` | none | Supports `filter`, `orderby`, `select`, `top`, `skip`, `resultFormat`. Key fields include `id`, `documentId`, `sequence`, `itemId`, `accountId`, `lineType`, `lineObjectNumber`, `description`, `quantity`, `directUnitCost`, discounts, tax amounts, `expectedReceiptDate`, `receivedQuantity`, `invoicedQuantity`, `invoiceQuantity`, `receiveQuantity`, `itemVariantId`, `locationId`. |
| `List_PurchaseOrderLinesOfPurchaseOrder_PAG30067` | `PurchaseOrder_id` | Same line fields as above, but scoped through parent PO id. This is the most practical native way to fetch lines for one PO. |
| `Create_PurchaseOrderLine_PAG30067` | none | Writable fields include `documentId`, `sequence`, `itemId`, `accountId`, `lineType`, `lineObjectNumber`, descriptions, unit of measure, quantity, costs, discounts, tax code, `expectedReceiptDate`, `invoiceQuantity`, `receiveQuantity`, `itemVariantId`, `locationId`. |
| `Create_PurchaseOrderLinesOfPurchaseOrder_PAG30067` | `PurchaseOrder_id` | Same writable fields as the standalone create action, but tied to a parent PO. |

### Vendors
| Action | Required params | Key request fields / behavior |
|---|---|---|
| `List_Vendors_PAG30010` | none | Supports `filter`, `orderby`, `select`, `top`, `skip`, `resultFormat`. Key fields: `id`, `number`, `displayName`, address parts, `phoneNumber`, `email`, `website`, `currencyId`, `currencyCode`, `paymentTermsId`, `paymentMethodId`, `taxLiable`, `blocked`, `balance`, `lastModifiedDateTime`. |
| `Create_Vendor_PAG30010` | none | Writable fields include `number`, `displayName`, address fields, phone/email/website, tax registration, currency, IRS1099 code, payment terms/method, `taxLiable`, `blocked`. |
| `List_Vendors_PAG20010` | none | Legacy read page with compact shape: `address` is flattened and there are fewer address-detail fields. |
| `List_Vendors_PAG30308` | none | Very compact vendor shape focused on city/state/country/payment info/balance. |
| `List_Vendors_PAG36959` | none | Small custom/alternate vendor projection using `vendorNo`, `vendorName`, posting group, and address data. |

### Items
| Action | Required params | Key request fields / behavior |
|---|---|---|
| `List_Items_PAG30008` | none | Supports `filter`, `orderby`, `select`, `top`, `skip`, `resultFormat`. Key fields: `id`, `number`, `displayName`, `displayName2`, `type`, `itemCategoryId`, `itemCategoryCode`, `blocked`, `gtin`, `inventory`, `unitPrice`, `priceIncludesTax`, `unitCost`, base unit of measure ids/codes, tax/inventory/general posting groups, `lastModifiedDateTime`. |
| `Create_Item_PAG30008` | none | Writable fields include number, descriptions, type, categories, blocked, GTIN, inventory, pricing/cost, tax group, base UOM, general product posting group, inventory posting group. |
| `Modify_Item_PAG30008` | `If-Match`, `id` | Same editable fields as create; requires `@odata.etag`. |
| `List_Items_PAG20008` | none | Legacy read page with fewer fields than `PAG30008` and `baseUnitOfMeasure` instead of `baseUnitOfMeasureCode`. |

### Posted purchase receipts (`PAG30064` / `PAG30065`)
| Action | Required params | Key request fields / behavior |
|---|---|---|
| `List_PurchaseReceipts_PAG30064` | none | Read-only. Supports `filter`, `orderby`, `select`, `top`, `skip`, `resultFormat`. Key fields: `id`, `number`, `invoiceDate`, `postingDate`, `dueDate`, `vendorNumber`, `vendorName`, pay-to/ship-to/buy-from address fields, `currencyCode`, `orderNumber`, `lastModifiedDateTime`. |
| `List_PurchaseReceiptLines_PAG30065` | none | Read-only. Key fields: `id`, `documentId`, `sequence`, `lineType`, `lineObjectNumber`, `description`, `description2`, `unitOfMeasureCode`, `unitCost`, `quantity`, `discountPercent`, `taxPercent`, `expectedReceiptDate`. |
| `List_PurchaseReceiptLinesOfPurchaseReceipt_PAG30065` | `PurchaseReceipt_id` | Same read-only line fields, scoped through a receipt id. |

### Inventory-adjacent schema surfaced
| Action | Required params | Key request fields / behavior |
|---|---|---|
| `List_ItemLedgerEntries_PAG30069` | none | Read-only inventory movement feed with `entryNumber`, `itemNumber`, `postingDate`, `entryType`, `sourceNumber`, `sourceType`, `documentNumber`, `documentType`, `description`, `quantity`, and actual cost/sales amounts. Useful for downstream reconciliation, but not a substitute for Item Journal Line APIs. |

## 3. Read validation results

### Purchase Orders — first 5
Query used:
```json
{"top":5,"orderby":"lastModifiedDateTime desc","select":"id,number,vendorNumber,vendorName,status,orderDate,requestedReceiptDate,fullyReceived,lastModifiedDateTime"}
```
Result:
- `@odata.count = 15`
- Sample rows:
  - `106030` — vendor `40000` / Wide World Importers / `status=Draft` / `fullyReceived=true`
  - `106029` — vendor `50000` / Nod Publishers / `status=Open` / `fullyReceived=true`
  - `106028` — vendor `50000` / Nod Publishers / `status=Open` / `fullyReceived=true`
  - `106027` — vendor `40000` / Wide World Importers / `status=Open` / `fullyReceived=true`
  - `106026` — vendor `40000` / Wide World Importers / `status=Open` / `fullyReceived=true`

### Specific Purchase Order by number
Query used:
```json
{"filter":"number eq '106030'","select":"id,number,vendorNumber,vendorName,status,orderDate,postingDate,requestedReceiptDate,fullyReceived,lastModifiedDateTime"}
```
Result:
- 1 record found
- PO `106030`
- `id = 9065b155-3b47-f111-a820-002248b5dea4`
- `vendorNumber = 40000`
- `vendorName = Wide World Importers`
- `postingDate = 2021-04-12`

### Purchase Order Lines for PO `106030`
Query used:
```json
{"PurchaseOrder_id":"9065b155-3b47-f111-a820-002248b5dea4","top":20,"orderby":"sequence asc","select":"id,documentId,sequence,lineType,lineObjectNumber,description,quantity,directUnitCost,expectedReceiptDate,receivedQuantity,invoicedQuantity,invoiceQuantity,receiveQuantity,locationId"}
```
Result:
- `@odata.count = 59`
- First lines returned successfully through the parent-scoped sub-entity action
- Examples:
  - Seq `10000` / item `11956002` / qty `4` / direct cost `11.28` / `receiveQuantity=4`
  - Seq `20000` / item `11956402` / qty `12` / direct cost `0.94` / `receiveQuantity=12`
  - Seq `30000` / item `11956302` / qty `12` / direct cost `0.94` / `receiveQuantity=12`

### Vendors — first 5
Query used:
```json
{"top":5,"orderby":"lastModifiedDateTime desc","select":"id,number,displayName,country,phoneNumber,email,blocked,lastModifiedDateTime"}
```
Result:
- `@odata.count = 8`
- Sample rows:
  - `V-HERSTERA` — Herstera Garden S.L.
  - `64000` — Hydropower Powerplant
  - `82000` — Subcontractor
  - `50000` — Nod Publishers
  - `40000` — Wide World Importers

### Items — first 5
Query used:
```json
{"top":5,"orderby":"lastModifiedDateTime desc","select":"id,number,displayName,type,inventory,baseUnitOfMeasureCode,unitCost,lastModifiedDateTime"}
```
Result:
- `@odata.count = 139`
- Sample rows:
  - `26904020` — Arbil 20x20cm / `type=Inventory` / `unitCost=11.76`
  - `27302019` — Licoa 19x16cm Blanco / `unitCost=5.85`
  - `27303027` — Pile 27x22cm Blanco / `unitCost=16.17`
  - `27602024` — Bowi Grea 24x13cm Taupe / `unitCost=7.45`
  - `27601025` — Grea 25x23cm Taupe / `unitCost=12.42`

### Posted Purchase Receipts — search/list
Query used:
```json
{"top":5,"orderby":"lastModifiedDateTime desc","select":"id,number,orderNumber,vendorNumber,vendorName,postingDate,lastModifiedDateTime"}
```
Result:
- `@odata.count = 239`
- Sample receipt rows:
  - `107239` — vendor `40000` / Wide World Importers / posting `2026-06-03`
  - `107238` — vendor `10000` / Fabrikam, Inc. / posting `2026-06-03`
  - `107237` — vendor `20000` / First Up Consultants / posting `2026-06-03`
  - `107236` — vendor `20000` / First Up Consultants / posting `2026-06-03`
  - `107235` — vendor `20000` / First Up Consultants / posting `2026-06-03`

### Purchase Receipt Lines — parent scoped
Query used:
```json
{"PurchaseReceipt_id":"bd8d6e93-9029-f111-9f24-7ced8dad939a","top":20,"orderby":"sequence asc","select":"id,documentId,sequence,lineType,lineObjectNumber,description,quantity,unitCost,expectedReceiptDate"}
```
Result:
- 2 lines returned for posted receipt `107239`
- Examples:
  - Seq `10000` / item `GRH-1001` / qty `100` / unit cost `299`
  - Seq `20000` / item `GRH-1000` / qty `50` / unit cost `199`

### Receipt filtering caveat
A targeted query for `orderNumber eq '106030'` returned **no results** even though PO `106030` exists. Recommendation: do not assume the CRONUS posted receipt records always preserve a usable `orderNumber` link for demo validation; plan to match via posted receipt data plus vendor/date/line details when necessary.

## 4. Latency observations
- MCP search, describe, and read invocations completed interactively in-session with no retries or timeouts.
- Exact millisecond timings are **not** exposed by the MCP tooling used here, so observations are qualitative rather than benchmark-grade.
- Small list calls (`top=5`) and parent-scoped line reads (`top=20`) felt suitable for agentic lookups. Broad semantic searches are noisier than they are slow.

## 5. What works vs. what is missing

### Works well natively
- Purchase order header reads with filtering, projection, ordering, and pagination.
- Purchase order line reads, especially via `List_PurchaseOrderLinesOfPurchaseOrder_PAG30067`.
- Vendor and item master data reads from standard `PAG30010` and `PAG30008` pages.
- Posted purchase receipt and posted purchase receipt line reads.
- Discovery of standard write-capable actions for purchase orders, purchase lines, vendors, and items.

### Missing / caveats
- No native **Warehouse Receipt** MCP action surfaced in this validation.
- No native **Item Journal Line** action surfaced; the closest inventory read action is `List_ItemLedgerEntries_PAG30069`, which is history/audit data, not an editable item-journal endpoint.
- Posted purchase receipts are read-only in the surfaced action set.
- The only bound purchase-order action surfaced was `ReceiveAndInvoice_PurchaseOrders_PAG30066`; no receive-only bound action was discovered.
- Semantic action discovery can return legacy or irrelevant pages, so Sprint 1 code should pin exact action names instead of relying on broad discovery prompts.

## 6. Sprint 1 recommendations
1. **Use native BC MCP directly for read-side validation** of purchase orders, PO lines, vendors, items, and posted purchase receipts.
2. **Pin to the standard APIV2 pages** (`PAG30066`, `PAG30067`, `PAG30010`, `PAG30008`, `PAG30064`, `PAG30065`) rather than legacy list pages unless a smaller projection is intentionally desired.
3. **Use parent-scoped sub-entity actions** (`List_PurchaseOrderLinesOfPurchaseOrder_PAG30067`, `List_PurchaseReceiptLinesOfPurchaseReceipt_PAG30065`) for per-document detail fetches.
4. **Treat posted purchase receipts as the native proof artifact** after receiving.
5. **Plan custom AL** if Sprint 1 or later requires:
   - warehouse receipt creation/posting,
   - item journal line operations,
   - receipt-only posting from a purchase order.
6. **Keep write validation in a separate, tightly scoped configuration** once the team is ready to test writes; this PoC confirmed read safety only.
