from typing import List
from fastapi import APIRouter, HTTPException, status
from app.models.common import ErrorResponse
from app.models.venue import VenueMetadata, VenueSummary
from app.services.venue_service import VenueNotFoundError, venue_service

router = APIRouter(prefix="/venues", tags=["Venues"])


@router.get(
    "",
    summary="List all registered venues",
    description="Returns a lightweight summary of all available venues for exploration.",
    response_model=List[VenueSummary],
)
async def list_venues() -> List[VenueSummary]:
    return venue_service.list_venues()


@router.get(
    "/{venue_id}",
    summary="Get venue metadata",
    description="Returns detailed metadata, 3D bounds, camera spawn point, and model URL for the given venue.",
    response_model=VenueMetadata,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Venue not found",
        }
    },
)
async def get_venue(venue_id: str) -> VenueMetadata:
    try:
        return venue_service.get_venue(venue_id)
    except VenueNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue '{venue_id}' does not exist.",
        )


@router.post(
    "/reload",
    summary="Reload venue registry",
    description="Re-scans the venues directory on disk to pick up newly added or modified venue configurations without restarting.",
    response_model=List[VenueSummary],
)
async def reload_venues() -> List[VenueSummary]:
    venue_service.load_all_venues()
    return venue_service.list_venues()
