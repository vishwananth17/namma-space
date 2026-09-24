from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.common import ErrorResponse, Point3D
from app.models.poi import (
    POICreate,
    POIResponse,
    POISpatialResponse,
    POIUpdate,
)
from app.services.poi_service import (
    CoordinatesOutOfBoundsError,
    DuplicatePOIError,
    POINotFoundError,
    poi_service,
)
from app.services.venue_service import VenueNotFoundError

router = APIRouter(prefix="/venues/{venue_id}/pois", tags=["POIs & Spatial Data"])


@router.post(
    "",
    summary="Create a new POI",
    description="Creates a new Point of Interest inside the venue. Validates that 3D coordinates fall within venue bounds.",
    response_model=POIResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_poi(
    venue_id: str,
    poi_in: POICreate,
    db: Session = Depends(get_db),
) -> POIResponse:
    try:
        record = poi_service.create_poi(db, venue_id, poi_in)
        return POIResponse.from_record(record)
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CoordinatesOutOfBoundsError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
    except DuplicatePOIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "",
    summary="List and spatially query POIs",
    description=(
        "Retrieve POIs in a venue with optional filtering by category, tag, or floor. "
        "Supports spatial queries: provide x, y, z, and radius to filter within distance, "
        "or nearest_k to find the closest POIs using an in-memory KD-Tree index."
    ),
    response_model=List[POISpatialResponse],
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def list_or_query_pois(
    venue_id: str,
    category: Optional[str] = Query(None, description="Filter by category (e.g. workstation, amenity)"),
    tag: Optional[str] = Query(None, description="Filter by specific tag"),
    floor: Optional[int] = Query(None, description="Filter by floor number"),
    x: Optional[float] = Query(None, description="Query center X (meters)"),
    y: Optional[float] = Query(None, description="Query center Y (meters)"),
    z: Optional[float] = Query(None, description="Query center Z (meters)"),
    radius: Optional[float] = Query(None, gt=0, description="Spatial query radius in meters"),
    nearest_k: Optional[int] = Query(None, gt=0, le=50, description="Find k closest POIs to (x, y, z)"),
    db: Session = Depends(get_db),
) -> List[POISpatialResponse]:
    try:
        # Check if spatial radius query
        if radius is not None and x is not None and z is not None:
            center = Point3D(x=x, y=y if y is not None else 0.0, z=z)
            return poi_service.query_radius(
                db, venue_id, center=center, radius=radius, category=category
            )

        # Check if nearest-k query
        if nearest_k is not None and x is not None and z is not None:
            query_pt = Point3D(x=x, y=y if y is not None else 0.0, z=z)
            return poi_service.query_nearest(
                db, venue_id, point=query_pt, k=nearest_k, category=category
            )

        # Standard list query
        records = poi_service.list_pois(
            db, venue_id, category=category, tag=tag, floor=floor
        )
        return [POISpatialResponse.from_record_with_dist(r) for r in records]
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{poi_id}",
    summary="Get single POI details",
    response_model=POIResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_poi(
    venue_id: str,
    poi_id: str,
    db: Session = Depends(get_db),
) -> POIResponse:
    try:
        record = poi_service.get_poi(db, venue_id, poi_id)
        return POIResponse.from_record(record)
    except (VenueNotFoundError, POINotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/{poi_id}",
    summary="Update an existing POI",
    description="Updates POI attributes. If new position is provided, coordinates are validated against venue bounds.",
    response_model=POIResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def update_poi(
    venue_id: str,
    poi_id: str,
    poi_in: POIUpdate,
    db: Session = Depends(get_db),
) -> POIResponse:
    try:
        record = poi_service.update_poi(db, venue_id, poi_id, poi_in)
        return POIResponse.from_record(record)
    except (VenueNotFoundError, POINotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CoordinatesOutOfBoundsError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )


@router.delete(
    "/{poi_id}",
    summary="Delete a POI",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def delete_poi(
    venue_id: str,
    poi_id: str,
    db: Session = Depends(get_db),
):
    try:
        poi_service.delete_poi(db, venue_id, poi_id)
    except (VenueNotFoundError, POINotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/bulk",
    summary="Bulk import POIs",
    description="Import multiple POIs at once from JSON array for rapid bulk tagging.",
    status_code=status.HTTP_200_OK,
)
async def bulk_import_pois(
    venue_id: str,
    items: List[Dict[str, Any]],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        count, errors = poi_service.bulk_import(db, venue_id, items)
        return {
            "status": "success",
            "imported_count": count,
            "errors_count": len(errors),
            "errors": errors,
        }
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
