import json
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.models.common import BoundingBox, Point3D
from app.models.venue import SpawnPoint, VenueMetadata, VenueSummary
from app.utils.logger import logger


class VenueNotFoundError(Exception):
    """Raised when a requested venue_id is not registered."""
    def __init__(self, venue_id: str):
        super().__init__(f"Venue with id '{venue_id}' was not found.")
        self.venue_id = venue_id


class VenueService:
    """Service for discovering, loading, and querying venue configurations and metadata."""

    def __init__(self, venues_dir: Optional[Path] = None):
        self.venues_dir = venues_dir or settings.VENUES_DIR
        self._venues: Dict[str, VenueMetadata] = {}
        self.load_all_venues()

    def load_all_venues(self) -> None:
        """Scan the venues directory and load all valid venue config.json files."""
        self._venues.clear()
        if not self.venues_dir.exists():
            logger.warning(f"Venues directory does not exist: {self.venues_dir}")
            return

        for item in self.venues_dir.iterdir():
            if item.is_dir():
                config_file = item / "config.json"
                if config_file.exists():
                    try:
                        venue_meta = self._parse_venue_config(item.name, config_file)
                        self._venues[venue_meta.id] = venue_meta
                        logger.info(f"Loaded venue: {venue_meta.id} ('{venue_meta.name}')")
                    except Exception as e:
                        logger.error(f"Failed to load venue from {config_file}: {e}", exc_info=True)

    def _parse_venue_config(self, folder_name: str, config_path: Path) -> VenueMetadata:
        """Parse and validate config.json file into VenueMetadata."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        venue_id = data.get("id", folder_name)
        model_file = data.get("model_file", "models/scene.glb")

        # Build bounds
        bounds_raw = data.get("bounds", {})
        min_pt = Point3D(**bounds_raw.get("min", {"x": -10.0, "y": 0.0, "z": -10.0}))
        max_pt = Point3D(**bounds_raw.get("max", {"x": 10.0, "y": 3.0, "z": 10.0}))
        bounds = BoundingBox.from_min_max(min_pt, max_pt)

        # Build spawn point
        spawn_raw = data.get("spawn_point", {})
        spawn_pos = Point3D(**spawn_raw.get("position", {"x": 0.0, "y": 1.6, "z": 0.0}))
        spawn_target = Point3D(**spawn_raw["target"]) if "target" in spawn_raw else None
        spawn_point = SpawnPoint(
            position=spawn_pos,
            target=spawn_target,
            yaw=spawn_raw.get("yaw", 0.0),
            pitch=spawn_raw.get("pitch", 0.0),
        )

        # Determine model format
        model_format = data.get("model_format")
        if not model_format:
            model_format = Path(model_file).suffix.lstrip(".").lower() or "glb"

        # Model URL served through static route
        # e.g., /static/venues/sample_lab/models/sample_room.glb
        clean_model_path = model_file.replace("\\", "/").lstrip("/")
        model_url = f"{settings.STATIC_URL_PREFIX}/venues/{venue_id}/{clean_model_path}"

        return VenueMetadata(
            id=venue_id,
            name=data.get("name", venue_id.replace("_", " ").title()),
            description=data.get("description"),
            model_format=model_format,
            units=data.get("units", "meters"),
            up_axis=data.get("up_axis", "Y"),
            floor_height=float(data.get("floor_height", 0.0)),
            bounds=bounds,
            spawn_point=spawn_point,
            model_filename=model_file,
            model_url=model_url,
            config=data,
        )

    def list_venues(self) -> List[VenueSummary]:
        """Return a list of all registered venues (lightweight summary)."""
        return [
            VenueSummary(
                id=v.id,
                name=v.name,
                description=v.description,
                model_format=v.model_format,
                units=v.units,
                up_axis=v.up_axis,
                floor_height=v.floor_height,
            )
            for v in self._venues.values()
        ]

    def get_venue(self, venue_id: str) -> VenueMetadata:
        """Fetch complete venue metadata by ID or raise VenueNotFoundError."""
        venue = self._venues.get(venue_id)
        if not venue:
            raise VenueNotFoundError(venue_id)
        return venue

    def get_venue_dir(self, venue_id: str) -> Path:
        """Get the physical folder path on disk for a venue."""
        path = self.venues_dir / venue_id
        if not path.exists():
            raise VenueNotFoundError(venue_id)
        return path

    def validate_point_in_bounds(self, venue_id: str, point: Point3D) -> bool:
        """Verify whether a 3D coordinate falls within venue boundaries."""
        venue = self.get_venue(venue_id)
        return venue.bounds.contains(point)


venue_service = VenueService()
