from typing import Any, Optional
from pydantic import BaseModel, Field


class Point3D(BaseModel):
    """3D point following Three.js convention: right-handed, Y-up, in meters."""
    x: float = Field(..., description="X coordinate in meters (east/west or width)")
    y: float = Field(..., description="Y coordinate in meters (vertical/height)")
    z: float = Field(..., description="Z coordinate in meters (north/south or depth)")

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]

    @classmethod
    def from_list(cls, coords: list[float]) -> "Point3D":
        if len(coords) != 3:
            raise ValueError("Point3D requires exactly 3 coordinates [x, y, z]")
        return cls(x=coords[0], y=coords[1], z=coords[2])


class BoundingBox(BaseModel):
    """Axis-Aligned Bounding Box (AABB) in 3D meters."""
    min: Point3D = Field(..., description="Minimum corner (x_min, y_min, z_min)")
    max: Point3D = Field(..., description="Maximum corner (x_max, y_max, z_max)")
    dimensions: Point3D = Field(..., description="Size along each axis (width, height, depth)")

    @classmethod
    def from_min_max(cls, min_pt: Point3D, max_pt: Point3D) -> "BoundingBox":
        dims = Point3D(
            x=round(max_pt.x - min_pt.x, 3),
            y=round(max_pt.y - min_pt.y, 3),
            z=round(max_pt.z - min_pt.z, 3),
        )
        return cls(min=min_pt, max=max_pt, dimensions=dims)

    def contains(self, point: Point3D, tolerance: float = 0.05) -> bool:
        """Check if point is within bounds with optional tolerance."""
        return (
            (self.min.x - tolerance) <= point.x <= (self.max.x + tolerance) and
            (self.min.y - tolerance) <= point.y <= (self.max.y + tolerance) and
            (self.min.z - tolerance) <= point.z <= (self.max.z + tolerance)
        )


class ErrorResponse(BaseModel):
    """Standardized API error response format across all endpoints."""
    error: str = Field(..., description="Machine-readable error code, e.g. NOT_FOUND")
    message: str = Field(..., description="Human-readable explanation of what went wrong")
    details: Optional[Any] = Field(None, description="Optional extra context, field errors, or validation details")
