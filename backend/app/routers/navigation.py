from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.algorithms.astar import NoPathFoundError, NoWalkableCellError
from app.db.session import get_db
from app.models.common import ErrorResponse
from app.models.navigation import (
    DynamicObstacle,
    DynamicObstacleCreate,
    NavMeshDebugInfo,
    NavigationRequest,
    NavigationResponse,
)
from app.services.navigation_service import navigation_service
from app.services.poi_service import POINotFoundError
from app.services.venue_service import VenueNotFoundError

router = APIRouter(prefix="/venues/{venue_id}", tags=["Navigation & Pathfinding"])


@router.post(
    "/navigate",
    summary="Compute obstacle-aware walking path",
    description=(
        "Calculates an obstacle-avoiding 3D walking route using 8-way A* pathfinding and line-of-sight smoothing. "
        "Origin and destination can be specified as POI IDs (e.g. 'workstation-alpha') or direct 3D coordinates. "
        "Returns ordered 3D waypoints, total distance, and estimated walking time."
    ),
    response_model=NavigationResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def navigate(
    venue_id: str,
    request: NavigationRequest,
    db: Session = Depends(get_db),
) -> NavigationResponse:
    try:
        return navigation_service.navigate(db, venue_id, request)
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except POINotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except NoPathFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except NoWalkableCellError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )


@router.get(
    "/navmesh/debug",
    summary="Get navigation grid debug visualization or metadata",
    description="Returns top-down 2D occupancy grid visualization image or metadata summary.",
    responses={
        200: {
            "content": {
                "image/png": {},
                "application/json": {},
            }
        },
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_navmesh_debug(
    venue_id: str,
    format: Optional[str] = Query(None, description="Set to 'image' to stream PNG directly"),
    accept: Optional[str] = Header(None),
):
    try:
        # Check if caller wants image
        if format == "image" or (accept and "image" in accept):
            img_path = navigation_service.get_debug_image_path(venue_id)
            return FileResponse(
                path=str(img_path),
                media_type="image/png",
                filename=f"{venue_id}_navmesh_debug.png",
            )
        # Otherwise return JSON info
        return navigation_service.get_debug_info(venue_id)
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/navmesh/debug.png",
    summary="Direct stream of navigation debug map PNG",
    response_class=FileResponse,
)
async def get_navmesh_debug_png(venue_id: str):
    try:
        img_path = navigation_service.get_debug_image_path(venue_id)
        return FileResponse(
            path=str(img_path),
            media_type="image/png",
            filename=f"{venue_id}_navmesh_debug.png",
        )
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# Dynamic Obstacles & Real-Time Rerouting Endpoints

@router.get(
    "/obstacles",
    summary="List active dynamic obstacles",
    description="Returns all dynamic temporary obstacles (e.g. liquid spills, construction) registered for this venue.",
    response_model=List[DynamicObstacle],
)
async def list_dynamic_obstacles(venue_id: str):
    try:
        return navigation_service.get_dynamic_obstacles(venue_id)
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/obstacles",
    summary="Register a dynamic obstacle",
    description="Injects a dynamic temporary obstacle into the venue navigation grid, prompting real-time rerouting.",
    response_model=DynamicObstacle,
    status_code=status.HTTP_201_CREATED,
)
async def create_dynamic_obstacle(venue_id: str, obstacle: DynamicObstacleCreate):
    try:
        return navigation_service.add_dynamic_obstacle(venue_id, obstacle)
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/obstacles/{obstacle_id}",
    summary="Remove a dynamic obstacle",
    description="Removes a dynamic obstacle by ID, restoring normal walkability in that region.",
)
async def delete_dynamic_obstacle(venue_id: str, obstacle_id: str):
    try:
        success = navigation_service.remove_dynamic_obstacle(venue_id, obstacle_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dynamic obstacle '{obstacle_id}' not found in venue '{venue_id}'.",
            )
        return {"status": "success", "message": f"Obstacle '{obstacle_id}' removed."}
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/obstacles/clear",
    summary="Clear all dynamic obstacles",
    description="Removes all dynamic obstacles registered for this venue.",
)
async def clear_dynamic_obstacles(venue_id: str):
    try:
        count = navigation_service.clear_dynamic_obstacles(venue_id)
        return {"status": "success", "cleared_count": count}
    except VenueNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

