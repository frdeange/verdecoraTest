from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.shared.auth.dependencies import get_current_user
from src.shared.auth.entra import AuthenticatedUser
from src.upload_web.models.upload import UploadSession
from src.upload_web.services.upload_session import create_upload_session, get_upload_session

router = APIRouter(prefix="/sessions", tags=["upload-web-api"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


@router.post("", response_model=UploadSession, status_code=status.HTTP_201_CREATED)
def create_session(current_user: CurrentUser) -> UploadSession:
    return create_upload_session(user_oid=current_user.oid, user_name=current_user.name)


@router.get("/{session_id}", response_model=UploadSession)
def read_session(session_id: str, current_user: CurrentUser) -> UploadSession:
    session = get_upload_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found.")
    if session.user_oid != current_user.oid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Upload session does not belong to the current user."
        )
    return session
