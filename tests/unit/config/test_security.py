import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import security  # noqa: E402


class ManagedIdentityCredentialTests(unittest.TestCase):
    def tearDown(self) -> None:
        security.get_managed_identity_credential.cache_clear()

    def test_uses_explicit_client_id_when_provided(self) -> None:
        captured_kwargs = {}

        class FakeDefaultAzureCredential:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch.object(security, "_load_symbol", return_value=FakeDefaultAzureCredential):
            credential = security.get_managed_identity_credential(client_id="mi-client-id")

        self.assertIsInstance(credential, FakeDefaultAzureCredential)
        self.assertEqual(
            captured_kwargs,
            {
                "exclude_interactive_browser_credential": True,
                "managed_identity_client_id": "mi-client-id",
            },
        )

    def test_falls_back_to_environment_client_id(self) -> None:
        captured_kwargs = {}

        class FakeDefaultAzureCredential:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch.dict(os.environ, {"AZURE_CLIENT_ID": "env-client-id"}, clear=False):
            with patch.object(security, "_load_symbol", return_value=FakeDefaultAzureCredential):
                security.get_managed_identity_credential()

        self.assertEqual(
            captured_kwargs,
            {
                "exclude_interactive_browser_credential": True,
                "managed_identity_client_id": "env-client-id",
            },
        )


class SecurityClientFactoryTests(unittest.TestCase):
    def test_get_keyvault_secret_reads_secret_value(self) -> None:
        credential = object()

        class FakeSecretClient:
            def __init__(self, *, vault_url, credential):
                self.vault_url = vault_url
                self.credential = credential

            def get_secret(self, name, version=None):
                return SimpleNamespace(
                    value=f"{name}:{version or 'latest'}:{self.vault_url}:{self.credential is credential}"
                )

        with patch.object(security, "_load_symbol", return_value=FakeSecretClient):
            secret_value = security.get_keyvault_secret(
                "bc-oauth-client-secret",
                vault_url="https://kv-verdecoratest.vault.azure.net/",
                credential=credential,
                version="v1",
            )

        self.assertEqual(
            secret_value,
            "bc-oauth-client-secret:v1:https://kv-verdecoratest.vault.azure.net/:True",
        )

    def test_get_cosmos_client_uses_managed_identity_credential(self) -> None:
        created_clients = []
        fake_credential = object()

        class FakeCosmosClient:
            def __init__(self, *, url, credential):
                created_clients.append({"url": url, "credential": credential})

        with patch.object(security, "_load_symbol", return_value=FakeCosmosClient):
            with patch.object(security, "get_managed_identity_credential", return_value=fake_credential):
                security.get_cosmos_client(endpoint="https://cosmos-verdecoratest.documents.azure.com:443/")

        self.assertEqual(
            created_clients,
            [
                {
                    "url": "https://cosmos-verdecoratest.documents.azure.com:443/",
                    "credential": fake_credential,
                }
            ],
        )

    def test_get_servicebus_client_uses_managed_identity_credential(self) -> None:
        created_clients = []
        fake_credential = object()

        class FakeServiceBusClient:
            def __init__(self, *, fully_qualified_namespace, credential):
                created_clients.append(
                    {
                        "fully_qualified_namespace": fully_qualified_namespace,
                        "credential": credential,
                    }
                )

        with patch.object(security, "_load_symbol", return_value=FakeServiceBusClient):
            with patch.object(security, "get_managed_identity_credential", return_value=fake_credential):
                security.get_servicebus_client(fully_qualified_namespace="sb-verdecoratest.servicebus.windows.net")

        self.assertEqual(
            created_clients,
            [
                {
                    "fully_qualified_namespace": "sb-verdecoratest.servicebus.windows.net",
                    "credential": fake_credential,
                }
            ],
        )

    def test_missing_environment_variable_raises_runtime_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                security.get_servicebus_client()


if __name__ == "__main__":
    unittest.main()
