from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
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
