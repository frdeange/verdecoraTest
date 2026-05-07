from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from src.shared.auth.entra import AuthenticatedUser
from src.upload_web.middleware import get_upload_current_user
from src.upload_web.services.upload_session import create_upload_session

router = APIRouter(tags=["upload-web"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_upload_current_user)]
POST_LOGIN_REDIRECT_PATH = "/dashboard"


def _build_template_context(
    request: Request,
    current_user: AuthenticatedUser,
    **extra: Any,
) -> dict[str, Any]:
    flash_messages = getattr(request.state, "flash_messages", [])
    context: dict[str, Any] = {
        "request": request,
        "current_user": current_user,
        "flash_messages": flash_messages,
    }
    context.update(extra)
    return context


def _microsoft_login_url() -> str:
    return f"/.auth/login/aad?{urlencode({'post_login_redirect_uri': POST_LOGIN_REDIRECT_PATH})}"


@router.get("/", response_class=HTMLResponse, include_in_schema=False, name="index")
@router.get("/login", response_class=HTMLResponse, include_in_schema=False, name="login")
async def landing_page(request: Request) -> Response:
    if request.headers.get("X-MS-TOKEN-AAD-ID-TOKEN") or getattr(request.state, "authenticated_user", None) is not None:
        return RedirectResponse(url=POST_LOGIN_REDIRECT_PATH, status_code=307)

    return request.app.state.templates.TemplateResponse(
        request,
        "pages/login.html",
        {
            "request": request,
            "page_title": "Iniciar sesión · Verdecora Upload Web",
            "login_url": _microsoft_login_url(),
            "flash_messages": getattr(request.state, "flash_messages", []),
        },
    )


@router.get("/dashboard", response_class=HTMLResponse, name="dashboard")
async def dashboard(request: Request, current_user: CurrentUser) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "pages/home.html",
        _build_template_context(
            request,
            current_user,
            page_title="Panel · Verdecora Upload Web",
        ),
    )


@router.get("/upload", response_class=HTMLResponse, name="upload_page")
@router.get("/uploads", response_class=HTMLResponse, include_in_schema=False)
async def upload_page(request: Request, current_user: CurrentUser) -> HTMLResponse:
    session = create_upload_session(user_oid=current_user.oid, user_name=current_user.name)
    return request.app.state.templates.TemplateResponse(
        request,
        "pages/upload.html",
        _build_template_context(
            request,
            current_user,
            page_title="Subir albarán · Verdecora Upload Web",
            session_id=session.session_id,
            files=session.files,
        ),
    )


@router.get("/mis-albaranes", response_class=HTMLResponse, name="my_uploads_page")
async def my_uploads_page(request: Request, current_user: CurrentUser) -> HTMLResponse:
    from src.upload_web.services.upload_session import get_all_user_sessions

    sessions = get_all_user_sessions(current_user.oid)
    uploads: list[dict[str, Any]] = []
    for s in sessions:
        for f in s.files:
            uploads.append(
                {
                    "session_id": s.session_id,
                    "filename": f.filename,
                    "status": s.status,
                    "albaran_group": f.albaran_group,
                    "uploaded_at": f.uploaded_at.strftime("%d/%m/%Y %H:%M"),
                    "content_type": f.content_type,
                }
            )

    return request.app.state.templates.TemplateResponse(
        request,
        "pages/my_albaranes.html",
        _build_template_context(
            request,
            current_user,
            page_title="Mis albaranes · Verdecora Upload Web",
            uploads=uploads,
        ),
    )


@router.get("/mis-albaranes/filter", response_class=HTMLResponse, name="my_uploads_filter")
async def my_uploads_filter(
    request: Request,
    current_user: CurrentUser,
    status_filter: str = "",
) -> HTMLResponse:
    from src.upload_web.services.upload_session import get_all_user_sessions

    sessions = get_all_user_sessions(current_user.oid)
    uploads: list[dict[str, Any]] = []
    for s in sessions:
        if status_filter and s.status != status_filter:
            continue
        for f in s.files:
            uploads.append(
                {
                    "session_id": s.session_id,
                    "filename": f.filename,
                    "status": s.status,
                    "albaran_group": f.albaran_group,
                    "uploaded_at": f.uploaded_at.strftime("%d/%m/%Y %H:%M"),
                    "content_type": f.content_type,
                }
            )

    return request.app.state.templates.TemplateResponse(
        request,
        "pages/my_albaranes.html",
        _build_template_context(
            request,
            current_user,
            page_title="Mis albaranes · Verdecora Upload Web",
            uploads=uploads,
            status_filter=status_filter,
        ),
    )


@router.get("/my-uploads")
async def my_uploads_partial(current_user: CurrentUser) -> dict[str, object]:
    return {
        "items": [],
        "user": {
            "oid": current_user.oid,
            "name": current_user.name,
        },
    }


@router.get("/upload/{session_id}/status", response_class=HTMLResponse, name="upload_status")
async def upload_status(request: Request, session_id: str, current_user: CurrentUser) -> HTMLResponse:
    """Show processing status with HTMX auto-refresh."""
    from src.upload_web.services.upload_session import get_upload_session

    session = get_upload_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_oid != current_user.oid:
        raise HTTPException(status_code=403, detail="Access denied.")

    total = len(session.files)
    completed = sum(1 for f in session.files if getattr(f, "processing_status", None) == "completed")
    progress = (completed / total * 100) if total > 0 else 0

    return request.app.state.templates.TemplateResponse(
        request,
        "pages/status.html",
        _build_template_context(
            request,
            current_user,
            page_title="Estado de procesamiento · Verdecora Upload Web",
            session=session,
            total=total,
            completed=completed,
            progress=round(progress, 1),
        ),
    )


@router.get("/upload/{session_id}/confirm-store", response_class=HTMLResponse, name="confirm_store")
async def confirm_store(request: Request, session_id: str, current_user: CurrentUser) -> HTMLResponse:
    """Show detected store, let user confirm or change."""
    from src.upload_web.services.upload_session import get_upload_session

    session = get_upload_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_oid != current_user.oid:
        raise HTTPException(status_code=403, detail="Access denied.")

    preflight = session.preflight
    return request.app.state.templates.TemplateResponse(
        request,
        "pages/confirm_store.html",
        _build_template_context(
            request,
            current_user,
            page_title="Confirmar tienda · Verdecora Upload Web",
            session=session,
            preflight=preflight,
        ),
    )


@router.get("/upload/{session_id}/summary", response_class=HTMLResponse, name="upload_summary")
async def upload_summary(request: Request, session_id: str, current_user: CurrentUser) -> HTMLResponse:
    """Show all uploaded files, preflight results, allow inline edits."""
    from src.upload_web.services.upload_session import get_upload_session

    session = get_upload_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_oid != current_user.oid:
        raise HTTPException(status_code=403, detail="Access denied.")

    return request.app.state.templates.TemplateResponse(
        request,
        "pages/summary.html",
        _build_template_context(
            request,
            current_user,
            page_title="Resumen de subida · Verdecora Upload Web",
            session=session,
        ),
    )
