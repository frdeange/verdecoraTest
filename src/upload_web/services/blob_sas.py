from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from azure.storage.blob import BlobSasPermissions, generate_blob_sas

from src.config.security import get_managed_identity_credential
from src.upload_web.config import UploadWebSettings, get_settings

SAS_EXPIRY_SECONDS = 900  # 15 minutes


def generate_upload_sas_url(
    session_id: str,
    filename: str,
    settings: UploadWebSettings | None = None,
) -> tuple[str, str, int]:
    """Generate a short-lived, write-only SAS URL for direct browser→blob upload.

    Returns (sas_url, blob_path, expires_in_seconds).
    Uses UserDelegationKey via DefaultAzureCredential — zero account keys.
    """
    resolved_settings = settings or get_settings()
    container = resolved_settings.raw_blob_container
    blob_path = f"{session_id}/{filename}"
    account_url = os.getenv("STORAGE_ACCOUNT_URL") or os.getenv("BLOB_ACCOUNT") or resolved_settings.blob_account

    if not account_url or account_url == "https://storage.example.com":
        return _build_mock_sas_url(container, blob_path)

    account_name = _extract_account_name(account_url)
    credential = get_managed_identity_credential()

    from azure.storage.blob import BlobServiceClient

    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)

    now = datetime.now(UTC)
    start_time = now - timedelta(minutes=5)
    expiry_time = now + timedelta(seconds=SAS_EXPIRY_SECONDS)

    delegation_key = blob_service_client.get_user_delegation_key(start_time, expiry_time)

    permissions = BlobSasPermissions(write=True, create=True)

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_path,
        user_delegation_key=delegation_key,
        permission=permissions,
        start=start_time,
        expiry=expiry_time,
        protocol="https",
    )

    sas_url = f"{account_url}/{container}/{blob_path}?{sas_token}"
    return sas_url, blob_path, SAS_EXPIRY_SECONDS


def _extract_account_name(account_url: str) -> str:
    """Extract storage account name from URL like https://acct.blob.core.windows.net."""
    parsed = urlparse(account_url)
    hostname = parsed.hostname or ""
    return hostname.split(".")[0]


def _build_mock_sas_url(container: str, blob_path: str) -> tuple[str, str, int]:
    """Return a mock SAS URL for local development without Azure Storage."""
    safe_expiry = (datetime.now(UTC) + timedelta(seconds=SAS_EXPIRY_SECONDS)).isoformat().replace("+00:00", "Z")
    mock_url = f"https://mock.blob.core.windows.net/{container}/{blob_path}?mock-sas&exp={safe_expiry}"
    return mock_url, blob_path, SAS_EXPIRY_SECONDS


__all__ = ["SAS_EXPIRY_SECONDS", "generate_upload_sas_url"]
