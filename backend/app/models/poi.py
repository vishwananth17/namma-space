import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.db.session import Base
from app.models.common import Point3D


class POIRecord(Base):
    """SQLAlchemy model for persistent POI storage."""
    __tablename__ = "pois"

    id = Column(String(64), primary_key=True)
    venue_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=True)
    pos_x = Column(Float, nullable=False)
    pos_y = Column(Float, nullable=False)
    pos_z = Column(Float, nullable=False)
    tags_json = Column(Text, nullable=False, default="[]")
    floor = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_pois_venue_category", "venue_id", "category"),
    )

    @property
    def tags(self) -> List[str]:
        try:
            return json.loads(self.tags_json) if self.tags_json else []
        except Exception:
            return []

    @tags.setter
    def tags(self, value: List[str]):
        self.tags_json = json.dumps(value or [])

    @property
    def position(self) -> Point3D:
        return Point3D(x=self.pos_x, y=self.pos_y, z=self.pos_z)


# --- Pydantic Schemas ---


class POIBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="POI display name")
    category: str = Field(
        ..., min_length=1, max_length=64, description="Category (e.g. workstation, amenity, exit, lab)"
    )
    description: Optional[str] = Field(None, description="Detailed description or instructions")
    position: Point3D = Field(..., description="3D coordinates in meters (Y-up)")
    tags: List[str] = Field(default_factory=list, description="Descriptive tags for search")
    floor: int = Field(0, description="Floor index or level (default 0)")


class POICreate(POIBase):
    id: Optional[str] = Field(
        None,
        description="Optional custom identifier (e.g. 'desk-01'). Auto-generated if omitted.",
    )


class POIUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = None
    position: Optional[Point3D] = None
    tags: Optional[List[str]] = None
    floor: Optional[int] = None


class POIResponse(POIBase):
    id: str = Field(..., description="Unique POI identifier")
    venue_id: str = Field(..., description="Parent venue identifier")
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: POIRecord) -> "POIResponse":
        return cls(
            id=record.id,
            venue_id=record.venue_id,
            name=record.name,
            category=record.category,
            description=record.description,
            position=record.position,
            tags=record.tags,
            floor=record.floor,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class POISpatialResponse(POIResponse):
    """POI response enriched with spatial distance metadata."""
    distance: Optional[float] = Field(
        None, description="Euclidean 3D distance in meters from query location"
    )

    @classmethod
    def from_record_with_dist(
        cls, record: POIRecord, distance: Optional[float] = None
    ) -> "POISpatialResponse":
        base = POIResponse.from_record(record)
        return cls(
            **base.model_dump(),
            distance=round(distance, 3) if distance is not None else None,
        )
