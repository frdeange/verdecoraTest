"""Route registration for Upload Web."""

from fastapi import APIRouter

from .api import router as api_router
from .auth import router as auth_router
from .upload import router as web_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(web_router)
router.include_router(api_router, prefix="/api")

__all__ = ["router"]
