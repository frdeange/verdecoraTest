from __future__ import annotations

from datetime import UTC, datetime, timedelta

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from src.config.security import get_managed_identity_credential


def generate_pdf_sas_url(storage_account_url: str, container: str, blob_name: str, expiry_hours: int = 1) -> str:
    """Generate a short-lived read-only SAS URL using a User Delegation Key."""

    if expiry_hours <= 0:
        raise ValueError("expiry_hours must be greater than zero.")

    credential = get_managed_identity_credential()
    blob_service_client = BlobServiceClient(account_url=storage_account_url, credential=credential)
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)

    start_time = datetime.now(UTC) - timedelta(minutes=5)
    expiry_time = start_time + timedelta(hours=expiry_hours, minutes=5)
    delegation_key = blob_service_client.get_user_delegation_key(start_time, expiry_time)
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=container,
        blob_name=blob_name,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(read=True),
        start=start_time,
        expiry=expiry_time,
        protocol="https",
    )
    return f"{blob_client.url}?{sas_token}"
