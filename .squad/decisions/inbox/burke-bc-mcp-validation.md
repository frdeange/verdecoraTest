# Burke — BC MCP validation against CRONUS

## Proposed decisions

### D-BURKE-BC-VALIDATION-001 — Standard native BC MCP pages are sufficient for Sprint 1 read-side validation
- **Decision:** Use native BC MCP standard pages `PAG30066`, `PAG30067`, `PAG30010`, `PAG30008`, `PAG30064`, and `PAG30065` for purchase-order, purchase-line, vendor, item, and posted-purchase-receipt reads.
- **Why:** Live CRONUS validation confirmed these actions are discoverable and readable with filtering, projection, ordering, pagination, and parent-scoped sub-entity patterns.

### D-BURKE-BC-VALIDATION-002 — Pin exact action names instead of relying on semantic discovery at runtime
- **Decision:** Treat semantic search as design-time discovery only; production code should call pinned action names.
- **Why:** Broad prompts such as `inventory` and `receipt` returned noisy legacy/intercompany/document actions alongside the relevant entities.

### D-BURKE-BC-VALIDATION-003 — Use parent-scoped sub-entity actions for detail reads
- **Decision:** Use `List_PurchaseOrderLinesOfPurchaseOrder_PAG30067` and `List_PurchaseReceiptLinesOfPurchaseReceipt_PAG30065` for document-detail fetches.
- **Why:** They worked cleanly in CRONUS once the parent id was known and provide the most direct document-centric read pattern for agents.

### D-BURKE-BC-VALIDATION-004 — Posted purchase receipts remain the canonical native proof artifact
- **Decision:** Treat posted purchase receipts and posted purchase receipt lines as the native confirmation artifact after receiving.
- **Why:** They are readable natively through MCP and match the intended downstream audit/confirmation use case.

### D-BURKE-BC-VALIDATION-005 — Plan custom AL for warehouse receipts, item journals, or receipt-only posting
- **Decision:** Do not assume native BC MCP covers warehouse receipt creation/posting, item journal lines, or receipt-only purchase-order posting.
- **Why:** This validation surfaced no native warehouse-receipt action, no native item-journal-line action, and only the `ReceiveAndInvoice_PurchaseOrders_PAG30066` bound action on purchase orders.

## Evidence captured
- Validation report: `docs/poc/bc-mcp-validation.md`
- PoC schema inventory: `src/poc/bc_mcp_poc/entity_schemas.py`
- PoC read demonstration: `src/poc/bc_mcp_poc/test_bc_read.py`
