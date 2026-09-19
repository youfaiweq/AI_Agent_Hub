"""System information endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/system", tags=["system"])


class SystemInfoResponse(BaseModel):
    """Public application metadata returned by the system endpoint."""

    name: str
    version: str
    environment: str


@router.get("/info", response_model=SystemInfoResponse, summary="Get application information")
async def get_system_info() -> SystemInfoResponse:
    """Return non-sensitive application metadata."""

    settings = get_settings()
    return SystemInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
