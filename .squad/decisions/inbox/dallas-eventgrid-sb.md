# Dallas — Event Grid → Service Bus runtime notes

## 2026-05-07
- Event Grid delivery to sb-albaranes-dev/albaran-incoming uses the system topic managed identity with deliveryWithResourceIdentity.
- Because sb-albaranes-dev has public network access disabled, trustedServiceAccessEnabled had to be enabled on the namespace network rule set and the system topic identity had to receive Azure Service Bus Data Sender on the target queue.
- The stable az eventgrid event-subscription create path failed for this combination (InvalidRequest), so runtime creation used ARM REST (2024-06-01-preview) instead.
- Smoke-test access to stalbaranesdev was opened only temporarily (public network access + CIDR allowlist + temporary Storage Blob Data Contributor for the signed-in user) and fully reverted after validation.

