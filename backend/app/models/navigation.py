from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field

from app.models.common import Point3D


class LocationInput(BaseModel):
    """Represents a location either as explicit 3D world coordinates or a POI id."""
    position: Optional[Point3D] = None
    poi_id: Optional[str] = None


class NavigationRequest(BaseModel):
    """Flexible navigation request supporting POI IDs or direct coordinates."""
    # Support both 'from'/'to' aliases and standard names
    start: Optional[Union[Point3D, str]] = Field(
        None,
        description="Origin: either a Point3D {x, y, z} or a POI id string (e.g. 'workstation-alpha')",
    )
    goal: Optional[Union[Point3D, str]] = Field(
        None,
        description="Destination: either a Point3D {x, y, z} or a POI id string (e.g. 'coffee-station')",
    )
    # Explicit aliases for convenience
    from_poi_id: Optional[str] = Field(None, description="Origin POI ID alias")
    to_poi_id: Optional[str] = Field(None, description="Destination POI ID alias")
    from_position: Optional[Point3D] = Field(None, description="Origin Point3D alias")
    to_position: Optional[Point3D] = Field(None, description="Destination Point3D alias")
    smooth_path: bool = Field(True, description="Apply line-of-sight path smoothing")
    agent_radius: Optional[float] = Field(None, description="Optional override for agent clearance (meters)")


class Waypoint3D(BaseModel):
    """An intermediate 3D node along the computed path."""
    x: float
    y: float
    z: float
    step_index: int


class NavigationResponse(BaseModel):
    """Complete navigation route payload for Three.js path rendering."""
    venue_id: str
    origin_name: str
    destination_name: str
    origin_snapped: bool = Field(..., description="Whether start position was snapped to nearest walkable cell")
    destination_snapped: bool = Field(..., description="Whether goal position was snapped to nearest walkable cell")
    waypoints: List[Point3D] = Field(..., description="Ordered 3D path waypoints for Three.js line/curve rendering")
    total_waypoints: int
    total_distance_meters: float
    estimated_walking_time_seconds: float
    execution_time_ms: float
    path_smoothed: bool


class NavMeshDebugInfo(BaseModel):
    """Metadata regarding the generated 2D occupancy grid."""
    venue_id: str
    grid_width: int
    grid_height: int
    cell_size: float
    walkable_cells_count: int
    obstacle_cells_count: int
    inflated_cells_count: int
    walkable_percentage: float
    debug_map_url: str
