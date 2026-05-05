from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.shared.auth.dependencies import get_current_user
from src.shared.auth.entra import AuthenticatedUser

router = APIRouter(tags=["upload-web"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "page_title": "Verdecora Upload Web",
            "hero_title": "Subida de albaranes",
            "hero_subtitle": "Scaffold inicial de la app FastAPI para la experiencia de subida en tienda.",
            "primary_action_href": "/uploads",
            "primary_action_label": "Ver placeholder de subida",
            "current_user": None,
        },
    )


@router.get("/uploads")
async def upload_placeholder(current_user: CurrentUser) -> dict[str, object]:
    return {
        "status": "placeholder",
        "message": "Los endpoints de subida se implementarán en el siguiente sprint.",
        "user": {
            "oid": current_user.oid,
            "name": current_user.name,
            "groups": list(current_user.groups),
        },
    }


@router.get("/mis-albaranes", response_class=HTMLResponse)
async def my_uploads_page(request: Request, current_user: CurrentUser) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "page_title": "Mis albaranes",
            "hero_title": "Mis albaranes",
            "hero_subtitle": "Panel placeholder para el seguimiento de cargas del usuario autenticado.",
            "primary_action_href": "/my-uploads",
            "primary_action_label": "Refrescar uploads",
            "current_user": current_user,
        },
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


@router.get("/logout", include_in_schema=False)
async def logout_placeholder() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=307)
