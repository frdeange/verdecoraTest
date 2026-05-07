from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.shared.auth.entra import AuthenticatedUser
from src.upload_web.middleware.session_security import get_upload_current_user
from src.upload_web.models.file_metadata import FileMetadata
from src.upload_web.models.preflight import PreflightResult
from src.upload_web.models.upload import UploadFile, UploadSession
from src.upload_web.services.blob_sas import generate_upload_sas_url
from src.upload_web.services.file_validator import validate_file
from src.upload_web.services.preflight import run_preflight
from src.upload_web.services.upload_session import create_upload_session, get_upload_session

router = APIRouter(prefix="/sessions", tags=["upload-web-api"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_upload_current_user)]

logger = logging.getLogger(__name__)


def _get_session_or_404(session_id: str) -> UploadSession:
    session = get_upload_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found.")
    return session


def _enforce_ownership(session: UploadSession, user: AuthenticatedUser) -> None:
    if session.user_oid != user.oid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload session does not belong to the current user.",
        )


@router.post("", response_model=UploadSession, status_code=status.HTTP_201_CREATED)
def create_session(current_user: CurrentUser) -> UploadSession:
    return create_upload_session(user_oid=current_user.oid, user_name=current_user.name)


@router.get("/{session_id}", response_model=UploadSession)
def read_session(session_id: str, current_user: CurrentUser) -> UploadSession:
    session = _get_session_or_404(session_id)
    _enforce_ownership(session, current_user)
    return session


@router.post("/{session_id}/sas")
def generate_sas(
    session_id: str,
    current_user: CurrentUser,
    filename: str = Query(min_length=1, max_length=255),
) -> dict[str, Any]:
    """Generate a short-lived, write-only SAS URL for direct browser-to-blob upload."""
    session = _get_session_or_404(session_id)
    _enforce_ownership(session, current_user)

    sas_url, blob_path, expires_in = generate_upload_sas_url(session_id, filename)

    if session.status in ("created", "draft"):
        session.status = "uploading"

    return {"upload_url": sas_url, "blob_path": blob_path, "expires_in": expires_in}


@router.post("/{session_id}/files", status_code=status.HTTP_201_CREATED)
def register_file(
    session_id: str,
    file_metadata: FileMetadata,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Register file metadata after a successful SAS upload."""
    session = _get_session_or_404(session_id)
    _enforce_ownership(session, current_user)

    current_session_bytes = sum(f.size_bytes for f in session.files)
    validation = validate_file(
        filename=file_metadata.filename,
        mime_type=file_metadata.mime_type,
        size_bytes=file_metadata.size_bytes,
        current_session_bytes=current_session_bytes,
    )
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": validation.errors},
        )

    file_id = str(uuid4())
    upload_file = UploadFile(
        file_id=file_id,
        filename=file_metadata.filename,
        blob_path=file_metadata.blob_path,
        content_type=file_metadata.mime_type,
        size_bytes=file_metadata.size_bytes,
        albaran_group=file_metadata.albaran_group,
        page_number=file_metadata.page_number,
    )
    session.files.append(upload_file)

    if session.status in ("created", "draft"):
        session.status = "uploading"

    return {"file_id": file_id, "status": "registered"}


@router.post("/{session_id}/preflight", response_model=PreflightResult)
def preflight_check(session_id: str, current_user: CurrentUser) -> PreflightResult:
    """Run a quick Document Intelligence heuristic on uploaded files."""
    session = _get_session_or_404(session_id)
    _enforce_ownership(session, current_user)

    if not session.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded to this session yet.",
        )

    doc_results: list[dict[str, Any]] | None = None
    from src.upload_web.config import get_settings

    settings = get_settings()
    if settings.docintell_endpoint:
        try:
            from src.upload_web.services.preflight import analyze_with_document_intelligence

            account_url = settings.blob_account
            container = settings.raw_blob_container
            doc_results = []
            for f in session.files[:5]:
                blob_url = f"{account_url}/{container}/{f.blob_path}"
                result = analyze_with_document_intelligence(blob_url, settings.docintell_endpoint)
                doc_results.append(result)
        except Exception:
            logger.warning("Document Intelligence analysis failed; falling back to heuristic.", exc_info=True)
            doc_results = None

    result = run_preflight(session, doc_results)

    from src.upload_web.models.upload import PreflightSummary

    session.preflight = PreflightSummary(
        detected_supplier=result.detected_supplier,
        detected_date=result.detected_date,
        detected_albaran_number=result.detected_albaran_number,
        detected_store=result.detected_store,
        confidence=result.confidence,
        is_albaran=result.is_albaran,
        warnings=result.warnings,
    )
    session.status = "preflight"

    return result


@router.post("/{session_id}/confirm")
def confirm_session(session_id: str, current_user: CurrentUser) -> dict[str, Any]:
    """Finalize a session: mark confirmed and publish to Service Bus."""
    session = _get_session_or_404(session_id)
    _enforce_ownership(session, current_user)

    if session.status == "confirmed":
        return {"status": "confirmed", "processing_started": False, "message": "Session was already confirmed."}

    if not session.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm a session with no files.",
        )

    session.status = "confirmed"
    session.confirmed_at = datetime.now(UTC)

    processing_started = _publish_to_service_bus(session)

    return {"status": "confirmed", "processing_started": processing_started}


@router.get("/{session_id}/status")
def session_status(session_id: str, current_user: CurrentUser) -> dict[str, Any]:
    """Return current session state, per-file status, and overall progress."""
    session = _get_session_or_404(session_id)
    _enforce_ownership(session, current_user)

    files_status = []
    completed_count = 0
    for f in session.files:
        file_state = getattr(f, "processing_status", None) or "pending"
        if file_state == "completed":
            completed_count += 1
        files_status.append(
            {
                "file_id": f.file_id,
                "filename": f.filename,
                "status": file_state,
                "blob_path": f.blob_path,
                "albaran_group": f.albaran_group,
            }
        )

    total = len(session.files)
    progress = (completed_count / total * 100) if total > 0 else 0

    return {
        "session_id": session.session_id,
        "status": session.status,
        "total_files": total,
        "completed_files": completed_count,
        "progress_percent": round(progress, 1),
        "files": files_status,
        "confirmed_at": session.confirmed_at.isoformat() if session.confirmed_at else None,
    }


def _publish_to_service_bus(session: UploadSession) -> bool:
    """Best-effort publish to Service Bus. Returns True on success."""
    from src.upload_web.config import get_settings

    settings = get_settings()
    if not settings.servicebus_namespace:
        logger.info("Service Bus not configured; skipping publish for session %s.", session.session_id)
        return False

    try:
        from src.config.security import get_servicebus_client

        sb_client = get_servicebus_client(fully_qualified_namespace=settings.servicebus_namespace)
        message_body = json.dumps(
            {
                "session_id": session.session_id,
                "user_oid": session.user_oid,
                "files": [f.model_dump(mode="json") for f in session.files],
                "confirmed_at": session.confirmed_at.isoformat() if session.confirmed_at else None,
                "preflight": session.preflight.model_dump(mode="json") if session.preflight else None,
            }
        )

        from azure.servicebus import ServiceBusMessage

        with sb_client.get_topic_sender(topic_name=settings.servicebus_topic) as sender:
            sender.send_messages(ServiceBusMessage(message_body))

        logger.info("Published session %s to Service Bus topic %s.", session.session_id, settings.servicebus_topic)
        return True
    except Exception:
        logger.error("Failed to publish session %s to Service Bus.", session.session_id, exc_info=True)
        return False
