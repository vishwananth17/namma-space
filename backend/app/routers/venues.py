from typing import List
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
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


@router.post(
    "/upload",
    summary="Upload 3D model or video to create a new indoor venue",
    description="Upload a .glb / .gltf 3D model or an indoor walkthrough video to automatically create, slice, and onboard a new navigable venue.",
    response_model=VenueMetadata,
)
async def upload_venue(
    venue_id: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
) -> VenueMetadata:
    import tempfile
    from pathlib import Path
    from scripts.onboard_venue import onboard_venue
    from scripts.process_video_to_3d import process_video_pipeline

    v_id = venue_id.strip().lower().replace(" ", "_")
    filename = file.filename or "model.glb"
    suffix = Path(filename).suffix.lower()

    temp_dir = Path(tempfile.gettempdir()) / "nammaspace_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"{v_id}_{filename}"

    with open(temp_file, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        if suffix in [".glb", ".gltf", ".ply", ".obj"]:
            onboard_venue(
                model_path_str=str(temp_file),
                venue_id=v_id,
                name=name,
                cell_size=0.15,
                agent_radius=0.3,
            )
        elif suffix in [".mp4", ".mov", ".mkv", ".avi"]:
            process_video_pipeline(
                venue_id=v_id,
                name=name,
                video_path=str(temp_file),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{suffix}'. Supported formats: .glb, .gltf, .ply, .obj, .mp4, .mov",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to onboard venue from uploaded file: {str(e)}",
        )

    venue_service.load_all_venues()
    return venue_service.get_venue(v_id)
