# Burke — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** BC/Dynamics Specialist
- **Stack:** Dynamics 365 Business Central, BC MCP Server, Purchase Orders, Item Journals
- **BC Tenant:** 562029ef-9022-45a6-b255-40cd71ebb2ce (CRONUS USA, Inc.)
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-03 — BC MCP / inventory analysis
- Reviewed the PRD assumptions for Purchase Orders, Purchase Lines, Vendors, Items, Warehouse Receipts, and Item Journals.
- Confirmed native BC MCP can expose standard top-level API pages for **Purchase Orders**, **Purchase Order Lines**, **Vendors**, **Items**, and **Posted Purchase Receipts**.
- Confirmed the standard API set does **not** expose a native top-level **Warehouse Receipt** API page, and does **not** expose **Item Journal Line** as a native item-journal API (standard `journalLines` is based on **Gen. Journal Line**).
- Confirmed the standard `purchaseOrder` API exposes the bound action **`receiveAndInvoice`**, but not a standard receive-only bound action.
- Documented that the correct receiving flow is **location-driven**: direct PO receipt for non-warehouse locations, Warehouse Receipt for locations that require receipt/put-away.
- Wrote detailed findings to `prerequisites/analysis/burke-bc-analysis.md`.

### 2026-05-04 — BC MCP validation against CRONUS
- Validated live native BC MCP discovery against `CRONUS USA, Inc.` using the configured production MCP endpoint in read-only mode.
- Confirmed native MCP discovery/actions for standard `PAG300xx` purchase orders, purchase order lines, vendors, items, and posted purchase receipts, plus multiple legacy/alternate vendor and item list pages.
- Successfully read the first 5 purchase orders, vendors, items, and posted purchase receipts; read PO `106030`; read 59 lines for PO `106030`; and read lines for posted receipt `107239`.
- Observed that semantic search is noisy for broad prompts (`inventory`, `receipt`) and that `orderNumber` filtering on posted purchase receipts is not reliable in CRONUS demo data.
- Wrote the validation report to `docs/poc/bc-mcp-validation.md` and the reusable PoC artifacts to `src/poc/bc_mcp_poc/`.
