from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.shared.auth.entra import AuthenticatedUser
from src.upload_web.middleware import get_upload_current_user

router = APIRouter(tags=["upload-web"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_upload_current_user)]


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


@router.get("/", response_class=HTMLResponse, include_in_schema=False, name="index")
async def index(request: Request, current_user: CurrentUser) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "pages/home.html",
        _build_template_context(
            request,
            current_user,
            page_title="Inicio · Verdecora Upload Web",
        ),
    )


@router.get("/upload", response_class=HTMLResponse, name="upload_page")
@router.get("/uploads", response_class=HTMLResponse, include_in_schema=False)
async def upload_page(request: Request, current_user: CurrentUser) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "pages/upload.html",
        _build_template_context(
            request,
            current_user,
            page_title="Subir albarán · Verdecora Upload Web",
        ),
    )


@router.get("/mis-albaranes", response_class=HTMLResponse, name="my_uploads_page")
async def my_uploads_page(request: Request, current_user: CurrentUser) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "pages/home.html",
        _build_template_context(
            request,
            current_user,
            page_title="Mis albaranes · Verdecora Upload Web",
            my_uploads_message="Tus albaranes enviados aparecerán aquí en el siguiente sprint. Mientras tanto, puedes seguir subiendo documentos desde el botón principal.",
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


@router.get("/logout", include_in_schema=False, name="logout_placeholder")
async def logout_placeholder() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)


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
