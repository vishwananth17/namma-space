from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.models.common import BoundingBox, Point3D


class SpawnPoint(BaseModel):
    """Initial camera/avatar spawn position and orientation for Three.js viewer."""
    position: Point3D = Field(..., description="Camera eye position in 3D meters")
    target: Optional[Point3D] = Field(
        None, description="Look-at target position in 3D meters"
    )
    yaw: Optional[float] = Field(0.0, description="Horizontal rotation in radians or degrees")
    pitch: Optional[float] = Field(0.0, description="Vertical tilt in radians or degrees")


class VenueSummary(BaseModel):
    """Lightweight venue summary for listing endpoints."""
    id: str = Field(..., description="Unique venue slug/identifier (e.g. 'sample_lab')")
    name: str = Field(..., description="Human-readable venue name")
    description: Optional[str] = Field(None, description="Short summary of the space")
    model_format: str = Field("glb", description="Model format: glb, gltf, ply, or obj")
    units: str = Field("meters", description="Measurement units (default: meters)")
    up_axis: str = Field("Y", description="Up-axis convention (Three.js standard: Y)")
    floor_height: float = Field(0.0, description="Reference floor plane height in meters")


class VenueMetadata(VenueSummary):
    """Complete venue metadata including bounds, spawn point, and model serving URL."""
    bounds: BoundingBox = Field(..., description="Axis-aligned bounding box enclosing the venue")
    spawn_point: SpawnPoint = Field(..., description="Default camera spawn position and target")
    model_filename: str = Field(..., description="Relative filename of the 3D model")
    model_url: str = Field(..., description="Public HTTP URL to download/stream the 3D model")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Raw configuration parameters and custom settings"
    )
