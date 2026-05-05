"""Route registration for Upload Web."""

from fastapi import APIRouter

from .auth import router as auth_router
from .upload import router as upload_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(upload_router)

__all__ = ["router"]
