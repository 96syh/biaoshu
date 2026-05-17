"""Health check API."""
from fastapi import APIRouter

from ..config import settings
from ..services.model_runtime_monitor import ModelRuntimeMonitor

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "model_runtime": ModelRuntimeMonitor.snapshot(),
    }
