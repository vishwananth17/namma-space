import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.common import Point3D
from app.models.poi import POICreate, POIRecord, POISpatialResponse, POIUpdate
from app.services.spatial_index import spatial_index_manager
from app.services.venue_service import VenueNotFoundError, venue_service
from app.utils.logger import logger


class POINotFoundError(Exception):
    def __init__(self, poi_id: str, venue_id: str):
        super().__init__(f"POI '{poi_id}' not found in venue '{venue_id}'.")
        self.poi_id = poi_id
        self.venue_id = venue_id


class CoordinatesOutOfBoundsError(Exception):
    def __init__(self, venue_id: str, point: Point3D, bounds_desc: str):
        msg = (
            f"Coordinates ({point.x}, {point.y}, {point.z}) are outside "
            f"the boundaries of venue '{venue_id}'. Venue bounds: {bounds_desc}"
        )
        super().__init__(msg)
        self.venue_id = venue_id
        self.point = point
        self.bounds_desc = bounds_desc


class DuplicatePOIError(Exception):
    def __init__(self, poi_id: str, venue_id: str):
        super().__init__(f"POI with id '{poi_id}' already exists in venue '{venue_id}'.")
        self.poi_id = poi_id
        self.venue_id = venue_id


def slugify(text: str) -> str:
    """Generate a clean URL/ID friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


class POIService:
    """Core domain service for POI persistence, coordinate bounds validation, and spatial querying."""

    def _ensure_venue_exists(self, venue_id: str):
        venue_service.get_venue(venue_id)

    def _validate_coordinates(self, venue_id: str, position: Point3D):
        venue = venue_service.get_venue(venue_id)
        if not venue.bounds.contains(position):
            bounds_desc = (
                f"X: [{venue.bounds.min.x}, {venue.bounds.max.x}], "
                f"Y: [{venue.bounds.min.y}, {venue.bounds.max.y}], "
                f"Z: [{venue.bounds.min.z}, {venue.bounds.max.z}]"
            )
            raise CoordinatesOutOfBoundsError(venue_id, position, bounds_desc)

    def _refresh_spatial_index_if_needed(self, db: Session, venue_id: str):
        index = spatial_index_manager.get_index(venue_id)
        if index.tree is None:
            records = (
                db.query(POIRecord)
                .filter(POIRecord.venue_id == venue_id)
                .all()
            )
            index.build(records)

    def create_poi(self, db: Session, venue_id: str, poi_in: POICreate) -> POIRecord:
        self._ensure_venue_exists(venue_id)
        self._validate_coordinates(venue_id, poi_in.position)

        poi_id = poi_in.id
        if not poi_id:
            poi_id = f"{slugify(poi_in.name)}-{uuid.uuid4().hex[:6]}"

        # Check uniqueness within venue
        existing = (
            db.query(POIRecord)
            .filter(POIRecord.venue_id == venue_id, POIRecord.id == poi_id)
            .first()
        )
        if existing:
            raise DuplicatePOIError(poi_id, venue_id)

        record = POIRecord(
            id=poi_id,
            venue_id=venue_id,
            name=poi_in.name,
            category=poi_in.category.lower().strip(),
            description=poi_in.description,
            pos_x=poi_in.position.x,
            pos_y=poi_in.position.y,
            pos_z=poi_in.position.z,
            floor=poi_in.floor,
        )
        record.tags = [t.lower().strip() for t in poi_in.tags]

        db.add(record)
        db.commit()
        db.refresh(record)

        spatial_index_manager.invalidate(venue_id)
        logger.info(f"Created POI '{record.id}' ('{record.name}') in venue '{venue_id}'.")
        return record

    def get_poi(self, db: Session, venue_id: str, poi_id: str) -> POIRecord:
        self._ensure_venue_exists(venue_id)
        record = (
            db.query(POIRecord)
            .filter(POIRecord.venue_id == venue_id, POIRecord.id == poi_id)
            .first()
        )
        if not record:
            raise POINotFoundError(poi_id, venue_id)
        return record

    def list_pois(
        self,
        db: Session,
        venue_id: str,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        floor: Optional[int] = None,
    ) -> List[POIRecord]:
        self._ensure_venue_exists(venue_id)
        query = db.query(POIRecord).filter(POIRecord.venue_id == venue_id)

        if category:
            query = query.filter(POIRecord.category == category.lower().strip())
        if floor is not None:
            query = query.filter(POIRecord.floor == floor)

        records = query.all()

        if tag:
            clean_tag = tag.lower().strip()
            records = [r for r in records if clean_tag in r.tags]

        return records

    def update_poi(
        self, db: Session, venue_id: str, poi_id: str, poi_in: POIUpdate
    ) -> POIRecord:
        record = self.get_poi(db, venue_id, poi_id)

        if poi_in.position is not None:
            self._validate_coordinates(venue_id, poi_in.position)
            record.pos_x = poi_in.position.x
            record.pos_y = poi_in.position.y
            record.pos_z = poi_in.position.z

        if poi_in.name is not None:
            record.name = poi_in.name
        if poi_in.category is not None:
            record.category = poi_in.category.lower().strip()
        if poi_in.description is not None:
            record.description = poi_in.description
        if poi_in.tags is not None:
            record.tags = [t.lower().strip() for t in poi_in.tags]
        if poi_in.floor is not None:
            record.floor = poi_in.floor

        db.commit()
        db.refresh(record)

        spatial_index_manager.invalidate(venue_id)
        logger.info(f"Updated POI '{poi_id}' in venue '{venue_id}'.")
        return record

    def delete_poi(self, db: Session, venue_id: str, poi_id: str) -> None:
        record = self.get_poi(db, venue_id, poi_id)
        db.delete(record)
        db.commit()

        spatial_index_manager.invalidate(venue_id)
        logger.info(f"Deleted POI '{poi_id}' from venue '{venue_id}'.")

    def query_radius(
        self,
        db: Session,
        venue_id: str,
        center: Point3D,
        radius: float,
        category: Optional[str] = None,
    ) -> List[POISpatialResponse]:
        """Find all POIs within a given radius (meters) using KD-Tree spatial index."""
        self._ensure_venue_exists(venue_id)
        self._refresh_spatial_index_if_needed(db, venue_id)

        index = spatial_index_manager.get_index(venue_id)
        matches = index.query_radius(center, radius)
        if not matches:
            return []

        # Map poi_id -> distance
        dist_map = dict(matches)
        id_list = list(dist_map.keys())

        query = db.query(POIRecord).filter(
            POIRecord.venue_id == venue_id,
            POIRecord.id.in_(id_list),
        )
        if category:
            query = query.filter(POIRecord.category == category.lower().strip())

        records = query.all()

        results = [
            POISpatialResponse.from_record_with_dist(r, dist_map.get(r.id))
            for r in records
        ]
        # Sort results by ascending distance
        results.sort(key=lambda x: x.distance or 0.0)
        return results

    def query_nearest(
        self,
        db: Session,
        venue_id: str,
        point: Point3D,
        k: int = 1,
        category: Optional[str] = None,
    ) -> List[POISpatialResponse]:
        """Find the k nearest POIs to a 3D coordinate using KD-Tree."""
        self._ensure_venue_exists(venue_id)
        self._refresh_spatial_index_if_needed(db, venue_id)

        index = spatial_index_manager.get_index(venue_id)
        # Fetch slightly more if filtering by category
        k_fetch = k * 3 if category else k
        matches = index.query_nearest(point, k=k_fetch)
        if not matches:
            return []

        dist_map = dict(matches)
        id_list = list(dist_map.keys())

        query = db.query(POIRecord).filter(
            POIRecord.venue_id == venue_id,
            POIRecord.id.in_(id_list),
        )
        if category:
            query = query.filter(POIRecord.category == category.lower().strip())

        records = query.all()

        results = [
            POISpatialResponse.from_record_with_dist(r, dist_map.get(r.id))
            for r in records
        ]
        results.sort(key=lambda x: x.distance or 0.0)
        return results[:k]

    def bulk_import(
        self, db: Session, venue_id: str, items: List[Dict[str, Any]]
    ) -> Tuple[int, List[str]]:
        """Import multiple POIs from parsed JSON/CSV dictionaries."""
        self._ensure_venue_exists(venue_id)
        imported_count = 0
        errors: List[str] = []

        for idx, item in enumerate(items):
            try:
                # Support nested position {x, y, z} or flat x, y, z columns
                if "position" in item:
                    pos = Point3D(**item["position"])
                else:
                    pos = Point3D(
                        x=float(item.get("x", item.get("pos_x"))),
                        y=float(item.get("y", item.get("pos_y", 0.0))),
                        z=float(item.get("z", item.get("pos_z"))),
                    )

                raw_tags = item.get("tags", [])
                if isinstance(raw_tags, str):
                    raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

                poi_create = POICreate(
                    id=item.get("id"),
                    name=item["name"],
                    category=item["category"],
                    description=item.get("description"),
                    position=pos,
                    tags=raw_tags,
                    floor=int(item.get("floor", 0)),
                )

                # Check if exists, update or create
                existing = (
                    db.query(POIRecord)
                    .filter(
                        POIRecord.venue_id == venue_id,
                        POIRecord.id == poi_create.id,
                    )
                    .first()
                    if poi_create.id
                    else None
                )

                if existing:
                    self.update_poi(
                        db,
                        venue_id,
                        existing.id,
                        POIUpdate(
                            name=poi_create.name,
                            category=poi_create.category,
                            description=poi_create.description,
                            position=poi_create.position,
                            tags=poi_create.tags,
                            floor=poi_create.floor,
                        ),
                    )
                else:
                    self.create_poi(db, venue_id, poi_create)

                imported_count += 1
            except Exception as e:
                errors.append(f"Row {idx + 1} ('{item.get('name', 'unnamed')}'): {str(e)}")

        return imported_count, errors


poi_service = POIService()
