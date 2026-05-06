from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas

from src.config.security import get_managed_identity_credential
from src.upload_web.config import UploadWebSettings, get_settings
from src.upload_web.models.upload import UploadSession

_UPLOAD_SESSIONS: dict[str, UploadSession] = {}


def create_upload_session(
    user_oid: str,
    user_name: str,
    settings: UploadWebSettings | None = None,
) -> UploadSession:
    resolved_settings = settings or get_settings()
    session_id = str(uuid4())
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(hours=1)
    session = UploadSession(
        session_id=session_id,
        user_oid=user_oid,
        user_name=user_name,
        created_at=created_at,
        status="created",
        files=[],
        container_name=resolved_settings.raw_blob_container,
        upload_prefix=_build_upload_prefix(session_id),
        sas_token=_generate_upload_sas(session_id, resolved_settings, expires_at),
        sas_expires_at=expires_at,
    )
    _UPLOAD_SESSIONS[session_id] = session
    return session


def get_upload_session(session_id: str) -> UploadSession | None:
    return _UPLOAD_SESSIONS.get(session_id)


def get_all_user_sessions(user_oid: str) -> list[UploadSession]:
    """Return all sessions belonging to the given user."""
    return [s for s in _UPLOAD_SESSIONS.values() if s.user_oid == user_oid]


def clear_upload_sessions() -> None:
    _UPLOAD_SESSIONS.clear()


def _build_upload_prefix(session_id: str) -> str:
    return f"{session_id}/"


def _generate_upload_sas(session_id: str, settings: UploadWebSettings, expiry: datetime) -> str:
    account_url = os.getenv("STORAGE_ACCOUNT_URL") or os.getenv("BLOB_ACCOUNT")
    if not account_url:
        return _build_mock_sas_token(session_id, expiry)

    credential = get_managed_identity_credential()
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
    start_time = datetime.now(UTC) - timedelta(minutes=5)
    delegation_key = blob_service_client.get_user_delegation_key(start_time, expiry)
    permissions = ContainerSasPermissions(read=True, write=True, create=True)
    sas_token = generate_container_sas(
        account_name=blob_service_client.account_name,
        container_name=settings.raw_blob_container,
        user_delegation_key=delegation_key,
        permission=permissions,
        start=start_time,
        expiry=expiry,
        protocol="https",
    )
    return sas_token


def _build_mock_sas_token(session_id: str, expiry: datetime) -> str:
    safe_expiry = expiry.isoformat().replace("+00:00", "Z")
    return f"mock-sas-session={session_id}&prefix={_build_upload_prefix(session_id)}&exp={safe_expiry}"


__all__ = ["clear_upload_sessions", "create_upload_session", "get_all_user_sessions", "get_upload_session"]
