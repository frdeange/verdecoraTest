from __future__ import annotations

import sys
from types import SimpleNamespace

from src.config import security


def test_get_managed_identity_credential_uses_default_azure_credential(
    monkeypatch,
) -> None:
    expected_credential = object()
    calls: list[dict[str, bool]] = []

    def fake_default_azure_credential(**kwargs: bool) -> object:
        calls.append(kwargs)
        return expected_credential

    monkeypatch.setitem(
        sys.modules,
        "azure.identity",
        SimpleNamespace(DefaultAzureCredential=fake_default_azure_credential),
    )
    security.get_managed_identity_credential.cache_clear()

    credential = security.get_managed_identity_credential()

    assert credential is expected_credential
    assert calls == [{"exclude_interactive_browser_credential": True}]

    security.get_managed_identity_credential.cache_clear()
