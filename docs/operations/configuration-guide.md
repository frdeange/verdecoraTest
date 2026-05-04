# Configuration guide

## Baseline

- **Python**: 3.12+
- **Region**: `swedencentral`
- **Resource group (dev)**: `rg-verdecoratest-dev`
- **Authentication**: Managed Identity everywhere; no shared keys in runtime paths

## Environment variables

### Shared Azure access

| Variable | Default | Purpose |
| --- | --- | --- |
| `AZURE_CLIENT_ID` | _(empty)_ | User-assigned managed identity selector when required |
| `AZURE_TENANT_ID` | `tenant-id` | Tenant used by the HITL webform JWT validator |
| `KEY_VAULT_URL` | required | Key Vault endpoint for runtime secret lookups |
| `COSMOS_ENDPOINT` | `https://localhost:8081` | Cosmos DB endpoint for services and MCP servers |
| `SERVICEBUS_FQ_NAMESPACE` | required in some services | Fully-qualified Service Bus namespace |
| `SERVICE_BUS_NAMESPACE` | `verdecora-dev` or service default | Short namespace used by orchestrator, HITL and Flow 0 |

### Agent runtime

| Variable | Default | Purpose |
| --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | `https://verdecora-openai-dev.openai.azure.com/` | Azure OpenAI endpoint |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | OpenAI API version |
| `DOCUMENT_INTELLIGENCE_ENDPOINT` | `https://verdecora-docintell-dev.cognitiveservices.azure.com/` | Agent-side Document Intelligence endpoint |
| `GPT5_DEPLOYMENT` | `gpt-5` | A1 extractor deployment |
| `GPT5_MINI_DEPLOYMENT` | `gpt-5-mini` | A2-A6 deployment |
| `SKIP_TRIAGE_SUPPLIERS` | _(empty)_ | Comma-separated suppliers that bypass A2 |

### Orchestrator

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXTRACTION_QUEUE_NAME` | `extraction` | Queue consumed by the orchestrator service |
| `HITL_QUEUE_NAME` | `hitl-review` | Queue used for manual-review handoff |
| `DATABASE_NAME` | `verdecora` | Cosmos database for processing records |
| `PROCESSING_CONTAINER_NAME` | `processing-records` | Cosmos container for orchestration state |
| `STORAGE_ACCOUNT_URL` | `https://examplestorage.blob.core.windows.net` | Blob endpoint for downloads |
| `DOCINTELL_ENDPOINT` | `https://example.cognitiveservices.azure.com/` | OCR endpoint used by orchestration service |
| `SERVICE_BUS_POLLING_ENABLED` | `true` | Enables the background queue consumer |
| `SERVICE_BUS_POLL_INTERVAL_SECONDS` | `5` | Poll cadence |
| `SERVICE_BUS_BATCH_SIZE` | `5` | Max messages read per poll |
| `MAX_DELIVERY_ATTEMPTS` | `5` | Processing retries before giving up |

### HITL webform

| Variable | Default | Purpose |
| --- | --- | --- |
| `HITL_DECISIONS_TOPIC_NAME` | `hitl-decisions` | Topic used to publish reviewer decisions |
| `HITL_WEBFORM_BASE_URL` | `https://hitl-webform.example.com` | Public URL inserted into notifications |
| `HITL_EXPECTED_AUDIENCE` | `api://verdecora-hitl` | Expected JWT audience |
| `HITL_REVIEWER_ROLE` | `Verdecora.StoreManager` | Role required to access review flows |
| `HITL_ALLOW_EMAIL_BEARER` | `false` | Local-only shortcut for synthetic bearer tokens |

### Escalation timer / communication

| Variable | Default | Purpose |
| --- | --- | --- |
| `HITL_REMINDER_AFTER_HOURS` | `24` | First reminder threshold |
| `HITL_ESCALATION_AFTER_HOURS` | `48` | Escalation threshold |
| `HITL_FINAL_AFTER_HOURS` | `72` | Final escalation threshold |
| `HITL_ESCALATION_BATCH_SIZE` | `100` | Max pending reviews processed per timer cycle |

### Flow 0 dedup job

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Flow 0 logging verbosity |
| `COSMOS_DATABASE_NAME` | `albaranes-db` | Cosmos DB used by dedup |
| `COSMOS_CONTAINER_NAME` | `albaranes` | Cosmos container used by dedup |
| `FLOW0_SOURCE_QUEUE_NAME` | `extraccion-queue` | Input queue |
| `FLOW0_TARGET_QUEUE_NAME` | `extraccion-in` | Output queue |

### MCP servers

| Variable | Default | Purpose |
| --- | --- | --- |
| `ACS_ENDPOINT` | required | ACS Email endpoint |
| `ACS_SENDER_ADDRESS` | required | ACS sender address/domain |
| `DOCINTELL_ENDPOINT` | required | Document Intelligence MCP endpoint |
| `BC_MCP_SERVER_URL` | `https://mcp.businesscentral.dynamics.com` | BC MCP base URL |
| `BC_MCP_TENANT_ID` | `562029ef-9022-45a6-b255-40cd71ebb2ce` | BC tenant |
| `BC_MCP_ENVIRONMENT_NAME` | `Production` | BC environment |
| `BC_MCP_COMPANY` | `CRONUS USA, Inc.` | BC company |
| `BC_MCP_CONFIGURATION_NAME` | `DefaultMCPKiko` | BC config name |
| `BC_MCP_SCOPE` | `https://mcp.businesscentral.dynamics.com/.default` | Token scope |
| `BC_MCP_TIMEOUT_SECONDS` | `30` | Timeout for BC operations |
| `BC_MCP_TOOL_LIST_VENDORS` | `List_Vendors_PAG30010` | Vendor lookup tool |
| `BC_MCP_TOOL_LIST_PURCHASE_ORDERS` | `List_PurchaseOrders_PAG30066` | PO lookup tool |
| `BC_MCP_TOOL_GET_PO_LINES` | `List_PurchaseOrderLinesOfPurchaseOrder_PAG30067` | PO line lookup tool |
| `BC_MCP_TOOL_LIST_ITEMS` | `List_Items_PAG30008` | Item lookup tool |
| `BC_MCP_TOOL_LIST_PURCHASE_RECEIPTS` | `List_PurchaseReceipts_PAG30064` | Posted receipt lookup tool |
| `BC_MCP_TOOL_CREATE_PURCHASE_RECEIPT` | `Create_PurchaseReceipt_PAG30064` | Receipt creation tool |
| `BC_MCP_TOOL_CREATE_PURCHASE_RECEIPT_LINE` | `Create_PurchaseReceiptLine_PAG30065` | Receipt line creation tool |
| `BC_MCP_TOOL_POST_PURCHASE_RECEIPT` | `ReceiveAndInvoice_PurchaseOrders_PAG30066` | Receipt posting tool |

## Threshold configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| Validation tolerance | **2%** | A4 validator tolerance for quantity, price and total comparisons |
| HITL escalation timers | **24h / 48h / 72h** | Reminder, escalation and final deadline |
| Auto-approve confidence threshold | **overall_match_pct > 0.95** | Validation result can proceed to A5 |
| HITL review band | **0.80 - 0.95** | Route to manual review |
| Reject band | **< 0.80** | Hard reject / human handling |
| Triage manual review threshold | **0.65** | Lower-confidence triage stays manual |
| Max concurrent processing | **3 orchestrator replicas / 3 Flow 0 executions / 1 HITL replica** | Current ACA scaling envelope |

## MCP server configuration

### BC MCP

- **Tenant**: `562029ef-9022-45a6-b255-40cd71ebb2ce`
- **Environment**: `Production`
- **Company**: `CRONUS USA, Inc.`
- **Configuration name**: `DefaultMCPKiko`
- **Auth**: managed identity obtains a token for `https://mcp.businesscentral.dynamics.com/.default`

### Cosmos MCP

- **Endpoint**: `COSMOS_ENDPOINT`
- **Database**: caller-provided at tool invocation time
- **Containers**: caller-provided at tool invocation time (`albaranes`, `processing-records`, `feature-flags`, etc.)
- **Auth**: `DefaultAzureCredential`

### Document Intelligence MCP

- **Endpoint**: `DOCINTELL_ENDPOINT`
- **Models**: `prebuilt-layout`, `prebuilt-invoice`, `prebuilt-document`
- **Auth**: `DefaultAzureCredential`

### ACS Email MCP

- **Endpoint**: `ACS_ENDPOINT`
- **Sender domain/address**: `ACS_SENDER_ADDRESS`
- **Auth**: `DefaultAzureCredential`

## Feature flags reference

Feature flags are stored in the `feature-flags` Cosmos container with `document_type = feature-flag`.

Recommended operational flags:

- `triage.enabled`
- `ocr.document_intelligence.enabled`
- `hitl.auto_approve.enabled`
- `inventory.posting.enabled`
- `communications.escalation.enabled`

Each flag supports contextual overrides via `overrides[].match`, for example by `supplier_id` or `store_id`.

## Per-supplier configuration options

Supplier-specific settings are stored as `document_type = supplier-config` documents and exposed by `get_supplier_config(supplier_id)`.

Suggested keys inside `configuration`:

- `ocr_model_id`
- `auto_approve_confidence_threshold`
- `skip_triage`
- `validation_tolerance_pct`
- `requires_hitl`
- `preferred_language`
- `notification_recipient_email`

## Azure resource configuration

| Resource | Current configuration |
| --- | --- |
| Storage account | `StorageV2`, `Standard_ZRS`, Hot tier, TLS 1.2, no public access |
| Service Bus | `Standard` tier |
| Log Analytics | `PerGB2018` |
| Key Vault | `standard`, RBAC enabled, purge protection on |
| Document Intelligence | `FormRecognizer`, `S0` |
| Azure OpenAI account | `S0`, managed identity enabled |
| GPT deployments | `GlobalStandard`, capacity `10` for `gpt-5` and `gpt-5-mini` |
| Orchestrator ACA | `0.5 CPU`, `1Gi`, `minReplicas 0`, `maxReplicas 3` |
| Flow 0 ACA Job | `0.25 CPU`, `0.5Gi`, `parallelism 1`, `maxExecutions 3` |
| HITL webform ACA | `0.25 CPU`, `0.5Gi`, `minReplicas 0`, `maxReplicas 1` |

## Operational recommendations

- Mantén Managed Identity como único método de autenticación en runtime.
- Cambia los valores por defecto antes de promocionar a `test` o `prod`.
- Versiona cualquier cambio de umbral o feature flag con referencia a incidencia o PR.
- Cuando un proveedor requiera trato especial, usa `supplier-config` antes de clonar lógica en prompts o código.
