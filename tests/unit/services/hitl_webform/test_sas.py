from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.hitl_webform import sas  # noqa: E402


@pytest.mark.unit
def test_generate_pdf_sas_url_uses_user_delegation_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBlobServiceClient:
        def __init__(self, *, account_url: str, credential: object) -> None:
            captured["account_url"] = account_url
            captured["credential"] = credential
            self.account_name = "stverdecora"

        def get_blob_client(self, *, container: str, blob: str):
            captured["blob_ref"] = (container, blob)
            return type("BlobClient", (), {"url": f"https://stverdecora.blob.core.windows.net/{container}/{blob}"})()

        def get_user_delegation_key(self, start, expiry):
            captured["delegation_window"] = (start, expiry)
            return "delegation-key"

    class FakeBlobSasPermissions:
        def __init__(self, *, read: bool) -> None:
            captured["read_permission"] = read

    def fake_generate_blob_sas(**kwargs: object) -> str:
        captured["sas_kwargs"] = kwargs
        return "sig=token"

    credential = object()
    monkeypatch.setattr(sas, "BlobServiceClient", FakeBlobServiceClient)
    monkeypatch.setattr(sas, "BlobSasPermissions", FakeBlobSasPermissions)
    monkeypatch.setattr(sas, "generate_blob_sas", fake_generate_blob_sas)
    monkeypatch.setattr(sas, "get_managed_identity_credential", lambda: credential)

    sas_url = sas.generate_pdf_sas_url(
        "https://stverdecora.blob.core.windows.net",
        "albaranes-raw",
        "alb-001.pdf",
    )

    assert captured["account_url"] == "https://stverdecora.blob.core.windows.net"
    assert captured["credential"] is credential
    assert captured["blob_ref"] == ("albaranes-raw", "alb-001.pdf")
    assert captured["read_permission"] is True
    assert captured["sas_kwargs"]["user_delegation_key"] == "delegation-key"
    assert sas_url.endswith("?sig=token")


@pytest.mark.unit
def test_generate_pdf_sas_url_rejects_non_positive_expiry() -> None:
    with pytest.raises(ValueError):
        sas.generate_pdf_sas_url("https://stverdecora.blob.core.windows.net", "albaranes-raw", "alb-001.pdf", 0)
