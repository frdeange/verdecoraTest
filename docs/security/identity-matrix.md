# Identity and RBAC Matrix

## Scope

- **Environment:** Development
- **Region:** Sweden Central
- **Resource group:** `rg-verdecoratest-dev`
- **Identity baseline:** User-assigned managed identities for Azure workloads; no shared keys in application code or infrastructure.
- **Key Vault authorization model:** Azure RBAC mode only.
- **BC MCP authentication:** OAuth 2.0 Authorization Code + PKCE with delegated user identity.

> **Exception handling:** `github-runner-pat` remains a temporary operational exception for bootstrap automation. HITL email and PDF access use managed identity end-to-end and do not require ACS connection strings or storage account keys.

## Managed identity matrix

| Service | Managed identity | Target resource | Role | Justification |
|---|---|---|---|---|
| Agentic orchestrator | `agentic-orchestrator` | Cosmos DB NoSQL account | Cosmos DB Built-in Data Contributor | Persist orchestration state, supplier reputation lookups, and workflow checkpoints without using account keys. |
| Agentic orchestrator | `agentic-orchestrator` | Service Bus namespace | Azure Service Bus Data Sender | Publish workflow state transitions and scheduled follow-up events. |
| Agentic orchestrator | `agentic-orchestrator` | Service Bus namespace | Azure Service Bus Data Receiver | Consume queue/topic messages that resume or advance orchestration. |
| Agentic orchestrator | `agentic-orchestrator` | Blob Storage account | Storage Blob Data Reader | Read inbound albarán PDFs and related blob metadata. |
| Agentic orchestrator | `agentic-orchestrator` | Key Vault | Key Vault Secrets User | Read BC OAuth client secret and any approved non-MI exceptions at runtime. |
| Agentic orchestrator | `agentic-orchestrator` | Azure Communication Services | Contributor | Send HITL emails through ACS while the platform lacks a narrower RBAC role for managed-identity email operations. |
| Communication agent | `communication-agent` | Azure Communication Services | Azure Communication Services Contributor | Send and manage HITL email traffic and related ACS configuration operations. |
| Communication agent | `communication-agent` | Cosmos DB NoSQL account | Cosmos DB Built-in Data Contributor | Persist outbound communication state, reminders, and approval metadata. |
| Communication agent | `communication-agent` | Service Bus namespace | Azure Service Bus Data Sender | Publish HITL reminders, escalations, and approval outcome events. |
| Communication agent | `communication-agent` | Key Vault | Key Vault Secrets User | Read approved secrets needed for BC delegated auth or controlled operational exceptions. |
| HITL web form | `hitl-webform` | Cosmos DB NoSQL account | Cosmos DB Built-in Data Contributor | Record operator decisions, comments, and audit timestamps. |
| HITL web form | `hitl-webform` | Blob Storage account | Storage Blob Data Contributor | Generate User Delegation Keys and serve read-only SAS URLs for original PDFs without storage account keys. |
| HITL web form | `hitl-webform` | Service Bus namespace | Azure Service Bus Data Sender | Resume workflows after human approval, rejection, or modification. |
| HITL web form | `hitl-webform` | Key Vault | Key Vault Secrets User | Read approved secret-backed configuration without embedding credentials in code. |
| Upload web app | `upload-web` | Cosmos DB NoSQL account | Cosmos DB Built-in Data Contributor | Persist upload session state in `upload-sessions` and query upload status without account keys. |
| Upload web app | `upload-web` | Blob Storage account | Storage Blob Data Contributor | Create upload payloads in `albaranes-raw` using managed identity instead of storage account keys. |
| Upload web app | `upload-web` | Blob Storage account | Storage Blob Delegator | Issue user delegation SAS tokens for browser/mobile uploads without exposing storage keys. |
| Upload web app | `upload-web` | Azure Container Registry | AcrPull | Pull the private `verdecora-upload-web` image into the ACA environment. |
| Flow 0 worker | `flow0-worker` | Cosmos DB NoSQL account | Cosmos DB Built-in Data Contributor | Write deduplication records and initial ingestion state. |
| Flow 0 worker | `flow0-worker` | Service Bus namespace | Azure Service Bus Data Sender | Publish `albaran.recibido` events after deduplication. |
| Flow 0 worker | `flow0-worker` | Blob Storage account | Storage Blob Data Reader | Read source PDFs and blob metadata during ingestion. |
| Flow 0 worker | `flow0-worker` | Key Vault | Key Vault Secrets User | Read approved non-MI exceptions from Key Vault without exposing them in deployments. |

## HITL security controls

- **Authentication:** the HITL web form validates Entra ID access tokens from the `Authorization` header against the tenant JWKS endpoint and enforces the `Verdecora.StoreManager` application role before allowing approve/reject/modify decisions.
- **PDF access:** reviewers receive short-lived, read-only SAS URLs generated with a User Delegation Key obtained through managed identity; storage account keys remain disabled.
- **Auditability:** every decision and every PDF access event is written to Cosmos DB with reviewer identity, IP address, action, and correlation ID.
- **Email domain:** development environments use the ACS Azure-managed sender domain (`AzureManagedDomain` / `*.azurecomm.net`). Production should switch to a customer-managed sender domain with DNS validation.

## BC OAuth 2.0 + PKCE configuration guide

1. **Create an Entra app registration dedicated to the BC MCP client.** Use a single-tenant app unless multi-tenant access is explicitly required.
2. **Configure delegated permissions only.** Request the minimum Business Central delegated scopes required for read/write receipt operations; do not enable app-only permissions.
3. **Enable Authorization Code + PKCE.** The MCP client must initiate the sign-in flow with a per-request code verifier/challenge pair and exchange the code server-side.
4. **Register redirect URIs for the MCP host.** Add the exact HTTPS callback URIs used by the BC MCP deployment; reject wildcard redirects.
5. **Store the client secret in Key Vault as `bc-oauth-client-secret`.** Treat it as a confidential-client secret, never as an application setting or pipeline variable.
6. **Bind access with RBAC and Conditional Access.** Restrict who can consent/use the app, require MFA for interactive sign-in, and keep audit logs enabled in Entra ID and Business Central.
7. **Preserve delegated-user auditability.** Every BC action must run on behalf of a signed-in user so receipt postings remain attributable to a person rather than a daemon identity.
8. **Disable unsupported fallback flows.** Do not enable ROPC, implicit flow, device code flow, or client-credentials-only automation for BC posting.

### Recommended BC MCP runtime settings

| Setting | Recommendation |
|---|---|
| Tenant scope | Single tenant, production tenant only |
| Redirect URIs | Explicit HTTPS MCP callback URIs per environment |
| Secret name | `bc-oauth-client-secret` |
| Token audience | Business Central API / MCP resource only |
| Token storage | In-memory/session only; never persist refresh tokens to logs or Cosmos |
| Proof key | Required on every authorization request |

## Key Vault secret rotation recommendations

| Secret | Rotation target | Policy recommendation |
|---|---|---|
| `bc-oauth-client-secret` | Every 90 days (or shorter if tenant policy requires it) | Maintain overlapping secret versions, rotate before expiry, validate the new secret in dev first, and alert at 30/7/1 days before expiration. |
| `github-runner-pat` | Every 7-30 days, bootstrap use only | Prefer GitHub App or OIDC as the long-term replacement; if PAT use is unavoidable, keep scopes minimal, short-lived, and monitored. |

### Operational controls

- Enable Key Vault diagnostics to Log Analytics and alert on `SecretNearExpiry`, `SecretGet`, and unauthorized access patterns.
- Monitor Entra sign-in logs for the HITL application and alert on denied requests caused by missing `Verdecora.StoreManager` role assignments.
- Track Cosmos audit writes and SAS generation events with correlation IDs so every reviewer action can be reconstructed end-to-end.
- Use Key Vault versioning so rotations do not require destructive updates.
- Require dual control for production secret rotation and document the rollback procedure before each change window.
- Review RBAC assignments quarterly to ensure every managed identity still needs its granted scope.
