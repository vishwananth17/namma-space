from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.common import Point3D


class SearchResultItem(BaseModel):
    """An individual search hit with relevance scoring and spatial position."""
    id: str = Field(..., description="Unique POI identifier")
    venue_id: str = Field(..., description="Venue identifier")
    name: str = Field(..., description="POI display name")
    category: str = Field(..., description="POI category")
    description: Optional[str] = Field(None, description="POI description")
    position: Point3D = Field(..., description="3D coordinates in meters (Three.js space)")
    tags: List[str] = Field(default_factory=list, description="Descriptive tags")
    floor: int = Field(0, description="Floor index")
    score: float = Field(..., description="Relevance match score (0.0 to 100.0)")
    matched_field: str = Field(
        ..., description="Primary field triggering match: 'name', 'tags', 'category', or 'description'"
    )
    distance: Optional[float] = Field(
        None, description="Euclidean distance in meters from user position, if supplied"
    )


class SearchResponse(BaseModel):
    """Envelope for search results with execution telemetry."""
    query: str = Field(..., description="Echoed input search query")
    venue_id: str = Field(..., description="Queried venue identifier")
    category_filter: Optional[str] = Field(None, description="Category filter applied, if any")
    total_results: int = Field(..., description="Total matching items found")
    results: List[SearchResultItem] = Field(..., description="Ranked search results")
    execution_time_ms: float = Field(..., description="Search algorithm execution time in ms")
