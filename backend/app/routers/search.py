from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.common import ErrorResponse, Point3D
from app.models.search import SearchResponse
from app.services.search_service import search_service
from app.services.venue_service import VenueNotFoundError

router = APIRouter(prefix="/venues/{venue_id}/search", tags=["Search"])


@router.get(
    "",
    summary="Typo-tolerant search across POIs",
    description=(
        "Fuzzy search across POIs with weighted relevance ranking (name > tags > category > description). "
        "Supports typo-tolerance, category filtering, optional user distance calculation, and sorting."
    ),
    response_model=SearchResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def search_pois(
    venue_id: str,
    q: str = Query("", description="Search term, keyword, or object name"),
    category: Optional[str] = Query(None, description="Filter results by category"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    user_x: Optional[float] = Query(None, description="User camera/avatar X position in meters"),
    user_y: Optional[float] = Query(None, description="User camera/avatar Y position in meters"),
    user_z: Optional[float] = Query(None, description="User camera/avatar Z position in meters"),
    sort_by: str = Query(
        "relevance",
        description="Ranking order: 'relevance' (highest match score) or 'distance' (closest to user)",
    ),
    db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        user_pos = None
        if user_x is not None and user_z is not None:
            user_pos = Point3D(x=user_x, y=user_y if user_y is not None else 0.0, z=user_z)

        return search_service.search(
            db=db,
            venue_id=venue_id,
            query=q,
            category_filter=category,
            user_position=user_pos,
            limit=limit,
            sort_by=sort_by,
        )
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
