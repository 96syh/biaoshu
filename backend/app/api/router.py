"""Top-level API router aggregation."""
from fastapi import APIRouter

from ..routers import (
    assets,
    config,
    content,
    document,
    document_upload,
    export,
    history_cases,
    outline,
    projects,
    review,
)

api_router = APIRouter()

api_router.include_router(config.router)
api_router.include_router(document_upload.router)
api_router.include_router(document.router)
api_router.include_router(assets.router)
api_router.include_router(review.router)
api_router.include_router(export.router)
api_router.include_router(outline.router)
api_router.include_router(content.router)
api_router.include_router(projects.router)
api_router.include_router(history_cases.router)
