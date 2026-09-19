"""Version 1 API router registration."""

from fastapi import APIRouter

from app.api.v1.routes.system import router as system_router

router = APIRouter()
router.include_router(system_router)
