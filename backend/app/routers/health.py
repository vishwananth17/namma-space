from typing import Any, Dict
from fastapi import APIRouter
from app.config import settings
from app.services.venue_service import venue_service

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check endpoint",
    description="Returns backend server status, active version, and registered venues count.",
    response_model=Dict[str, Any],
)
async def health_check() -> Dict[str, Any]:
    venues = venue_service.list_venues()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENV,
        "registered_venues_count": len(venues),
        "venue_ids": [v.id for v in venues],
    }
