# Newt — MCP Landscape Analysis

## 1. Available Native MCP Tools

### 1.1 Azure-native MCP tools visible in this environment
The following `azure-*` tools are available here and represent the native Azure MCP capability surface currently exposed to this project:

- `azure-acr`
- `azure-advisor`
- `azure-aks`
- `azure-appconfig`
- `azure-applens`
- `azure-applicationinsights`
- `azure-appservice`
- `azure-azd`
- `azure-azurebackup`
- `azure-azuremigrate`
- `azure-azureterraform`
- `azure-azureterraformbestpractices`
- `azure-bicepschema`
- `azure-cloudarchitect`
- `azure-communication`
- `azure-compute`
- `azure-confidentialledger`
- `azure-containerapps`
- `azure-cosmos`
- `azure-datadog`
- `azure-deploy`
- `azure-deviceregistry`
- `azure-documentation`
- `azure-eventgrid`
- `azure-eventhubs`
- `azure-extension_azqr`
- `azure-extension_cli_generate`
- `azure-extension_cli_install`
- `azure-fileshares`
- `azure-foundry`
- `azure-foundryextensions`
- `azure-functionapp`
- `azure-functions`
- `azure-get_azure_bestpractices`
- `azure-grafana`
- `azure-group_list`
- `azure-group_resource_list`
- `azure-keyvault`
- `azure-kusto`
- `azure-loadtesting`
- `azure-managedlustre`
- `azure-marketplace`
- `azure-monitor`
- `azure-mysql`
- `azure-policy`
- `azure-postgres`
- `azure-pricing`
- `azure-quota`
- `azure-redis`
- `azure-resourcehealth`
- `azure-role`
- `azure-search`
- `azure-servicebus`
- `azure-servicefabric`
- `azure-signalr`
- `azure-speech`
- `azure-sql`
- `azure-storage`
- `azure-storagesync`
- `azure-subscription_list`
- `azure-virtualdesktop`
- `azure-wellarchitectedframework`
- `azure-workbooks`

### 1.2 Coverage check for the PRD services

| Service needed by PRD | Native Azure MCP present here? | Notes |
|---|---|---|
| Blob Storage | **Partial yes** | `azure-storage` exists. The learned commands clearly cover storage accounts and blob/container inspection, plus upload. The surfaced blob command returns blob metadata/properties; I did **not** find a clearly exposed binary-download/content-read command in this environment. |
| Cosmos DB | **Partial yes** | `azure-cosmos` exists, but the surfaced commands here are `cosmos_list` and `cosmos_database_container_item_query` (read/query oriented). I did **not** find native item create/update/delete commands in this environment. |
| Document Intelligence | **No dedicated native MCP tool found** | There is no `azure-document-intelligence` / `azure-form-recognizer` style tool exposed here. Document Intelligence exists as an Azure service, but not as a first-class native Azure MCP tool in this environment. |

### 1.3 Bottom line on Azure-native MCP reuse
- **Blob Storage:** reuse native Azure MCP where possible, but validate whether binary payload retrieval is required.
- **Cosmos DB:** native Azure MCP is useful for inspection/query, but not sufficient by itself for the PRD's write-heavy state management.
- **Document Intelligence:** this is the clearest gap; a wrapper/custom integration is still needed.

## 2. BC MCP Server Capabilities

### 2.1 Native BC MCP server status
Business Central now has a **native MCP server**. It is not hypothetical and does not require building a separate MCP server from scratch.

- Endpoint: `https://mcp.businesscentral.dynamics.com`
- It supports Microsoft clients and non-Microsoft MCP clients.
- By default it gives **read-only** access to exposed Business Central API pages.
- Write operations are enabled by configuration, not by building a different server.

### 2.2 How it exposes tools
The BC MCP server exposes **API page objects** as MCP tools.

- Admins can add individual API pages or use **Add All Standard APIs as Tools**.
- Only **top-level API pages** are supported as MCP tools (`ListPart` and `CardPart` are not).
- With **Unblock Edit Tools = ON**, the config can selectively allow:
  - Read
  - Create
  - Modify
  - Delete
  - Bound actions

When dynamic tool mode is off, tool names follow patterns such as:
- `List<object_name>_PAG<ID>`
- `Create<object_name>_PAG<ID>`
- `ListUpdate<object_name>_PAG<ID>`
- `Delete<object_name>_PAG<ID>`
- `<bound_action_name>_PAG<ID>`

### 2.3 Entities relevant to this PRD
#### Clearly supported natively through standard APIs / MCP configuration
- **Purchase Orders** — official v2 resource exists with `GET`, `POST`, `PATCH`, `DELETE`
- **Purchase Order Lines** — official v2 resource exists
- **Items** — official v2 resource exists
- **Vendors** — standard BC APIs exist and can be exposed through MCP configuration

#### Inventory / receiving entities
- **Purchase Orders** also expose a bound action `receiveAndInvoice`.
- I did **not** find an official Learn page for a standard v2 API resource dedicated to **Warehouse Receipt** / **Posted Warehouse Receipt** comparable to the purchaseOrder resource docs.
- I found functional warehouse documentation, but not a clearly documented standard MCP-ready API resource for warehouse receipts.
- I found standard API docs for **journalLine**, but not a specific official v2 resource page proving a ready-made **Item Journal Line** API tailored to the warehouse receiving scenario in the PRD.

### 2.4 Practical interpretation for this project
- **Agent 2 (read validation)** fits the native BC MCP server very well.
- **Agent 3 (inventory receiving)** is only **partially native**:
  - if standard BC APIs + bound actions are enough for your exact receiving flow, native BC MCP may suffice;
  - if you must create/post warehouse receipts with strict idempotence and minimum privilege, you will likely need a **small BC extension** (custom API page and/or bound action) and then expose that through the **native BC MCP server**.

That means the likely custom work is **inside Business Central**, not a separate external MCP server.

### 2.5 Authentication
BC MCP authentication is documented and is **OAuth 2.0 Authorization Code + PKCE** with Microsoft Entra ID.

For non-Microsoft MCP clients:
- Register an app in Microsoft Entra ID.
- Add delegated permissions for **Dynamics 365 Business Central**:
  - `user_impersonation`
  - `Financials.ReadWrite.All`
- Grant admin consent.
- Connect with scope:
  - `https://mcp.businesscentral.dynamics.com/.default`

Other connection settings:
- Authorization endpoint: `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize`
- Token endpoint: `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token`

Important implications:
- This is **user-delegated** access tied to the signed-in user's BC permissions.
- The docs emphasize user identity and auditability.
- This is **not** described as an app-only / managed identity BC MCP flow.

### 2.6 Your provided BC config mapped to actual headers
Provided:
- `TenantId=562029ef-9022-45a6-b255-40cd71ebb2ce`
- `Env=Production`
- `Company=CRONUS USA Inc.`
- `Config=DefaultMCPKiko`

BC docs use these actual headers:
- `TenantId: 562029ef-9022-45a6-b255-40cd71ebb2ce`
- `EnvironmentName: Production`
- `Company: CRONUS USA Inc.`
- `ConfigurationName: DefaultMCPKiko`

So `Env` should map to `EnvironmentName`, and `Config` should map to `ConfigurationName`.

## 3. MCP Decision Matrix

| MCP Server | Native Available? | Custom Needed? | Justification |
|---|---|---|---|
| `mcp-blob-storage` | **Partial** | **Maybe thin adapter, but not necessarily a full custom MCP server** | Native Azure Storage MCP exists (`azure-storage`), so do **not** assume a bespoke storage MCP is needed. However, the exposed tool surface here is metadata/list/upload oriented; I did not verify blob-content download. If Agent 1 only needs blob identity/URI for downstream processing, native is enough. If it must fetch bytes through MCP, a thin adapter may still be required. |
| `mcp-document-intelligence` | **No** | **Yes** | I found no dedicated native Azure Document Intelligence MCP tool in this environment. This is the strongest case for a custom wrapper/integration. |
| `mcp-cosmos-db` | **Partial** | **Yes, for writes** | Native `azure-cosmos` exists, but the surfaced commands here are list/query only. The PRD requires create/read/update state transitions across agents, so a write-capable adapter is still needed unless persistence is moved out of MCP. |
| `mcp-business-central-read` | **Yes** | **No** | Native BC MCP is a good fit for read-only access to purchase orders, purchase lines, vendors, and items. This should be implemented as a BC MCP configuration, not a custom external MCP server. |
| `mcp-business-central-inventory` | **Partial** | **Yes, but likely as BC API extension rather than standalone MCP server** | Native BC MCP can expose write tools and bound actions, but warehouse receipt / inventory-posting flows do not appear fully covered by the standard documented API surface. Best path: keep the native BC MCP server and add only the missing BC API page/action. |
| `mcp-teams` | **No** | **Yes** | WorkIQ is not a Teams messaging/action runtime. For Adaptive Cards + `Action.Submit` + webhook/HITL, you still need a Teams-capable implementation (Bot Framework, Graph/Power Automate, or a thin MCP wrapper over one of those). |

## 4. Teams / WorkIQ Analysis

### 4.1 What WorkIQ can do here
The available `workiq-*` tools are oriented to:
- asking Microsoft 365 Copilot questions about emails, meetings, files, and M365 context;
- generating conversation links for sharing/debug.

That makes WorkIQ useful for **information retrieval** from M365.

### 4.2 What WorkIQ does not solve for this PRD
I found no capability indicating that WorkIQ can:
- send proactive Teams messages;
- render or send **Adaptive Cards**;
- receive **`Action.Submit`** payloads;
- act as a Teams bot endpoint;
- manage approval state transitions triggered from Teams UI interactions.

### 4.3 Conclusion on Teams
**WorkIQ cannot replace the PRD's Teams HITL mechanism.**

If the system must:
- send Adaptive Cards,
- collect human approval/rejection/corrections,
- receive submit payloads,
- and trigger the next step,

then you still need a **Teams-capable bot/workflow integration**.

### 4.4 Lowest-custom approach
The lowest-custom option is **not** WorkIQ. It is one of these:
1. **Power Automate / Teams workflow + webhook/backend**
2. **Azure Bot Service / Bot Framework**
3. **Microsoft Graph-based Teams app/bot**

If the agent layer must call this over MCP, then wrap that implementation in a **thin `mcp-teams` adapter**.

## 5. Authentication Strategy

### 5.1 BC MCP
- Auth model: **OAuth 2.0 Authorization Code with PKCE**
- Identity provider: **Microsoft Entra ID**
- Client type: user-interactive MCP clients
- Required delegated BC permissions for non-Microsoft clients:
  - `user_impersonation`
  - `Financials.ReadWrite.All`
- MCP scope requested by the client:
  - `https://mcp.businesscentral.dynamics.com/.default`
- Authorization is executed with the **user identity**, so BC permission sets and audit trails remain authoritative.

### 5.2 Azure-native MCP tools
Official Azure MCP docs state that Azure MCP uses:
- **Azure user credentials** or
- **Managed identity**

and secures access through **Azure RBAC**.

Common parameters exposed by Azure MCP tools in this environment include:
- subscription
- resource group
- tenant
- auth method = `credential` / `key` / `connectionString`

Interpretation for this project:
- For production Azure-hosted services, prefer **managed identity + RBAC**.
- Use access keys / connection strings only where the native tool or SDK requires them and only as an exception.
- For Blob/Cosmos custom adapters, design around **Managed Identity** if they run in Azure Container Apps / Functions.

## 6. Recommendations

1. **Do not build separate custom MCP servers for Business Central read access.** Use the native BC MCP server.
2. **Split BC into two configurations, not two servers:**
   - a read-only configuration for Agent 2;
   - a write-limited configuration for Agent 3.
3. **Treat BC inventory as a BC-extension problem, not an MCP-server problem.** If standard APIs are insufficient, add a small AL API page / bound action and expose it through native BC MCP.
4. **Assume Document Intelligence still needs custom integration.** This is the clearest native gap.
5. **Assume Cosmos needs a write-capable adapter unless state persistence moves outside MCP.** Native Azure MCP here looks read/query oriented.
6. **Do not count on WorkIQ for HITL.** It does not replace a Teams bot, Adaptive Card sender, or submit-handler.
7. **Prefer managed identity for Azure-side custom components** and delegated OAuth for BC MCP.
8. **Most likely final architecture:**
   - native Azure MCP reused where it is genuinely sufficient;
   - native BC MCP reused for all BC access;
   - custom work limited to:
     - Document Intelligence wrapper,
     - Cosmos write adapter,
     - Teams HITL adapter,
     - optional BC API extension for warehouse receipt/inventory posting.

## Recommended decision in one sentence
**Kiko's suspicion is directionally correct for Business Central read access, but not for the whole landscape: native BC MCP can replace both BC "servers" conceptually, while Document Intelligence, Teams HITL, and probably Cosmos writes still need custom integration.**
