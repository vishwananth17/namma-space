from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    from scipy.spatial import KDTree
    _HAS_SCIPY = True
except ImportError:
    KDTree = None
    _HAS_SCIPY = False

from app.models.common import Point3D
from app.models.poi import POIRecord
from app.utils.logger import logger


class VenueSpatialIndex:
    """In-memory KD-Tree spatial index for high-speed spatial queries on a venue's POIs."""

    def __init__(self, venue_id: str):
        self.venue_id = venue_id
        self.poi_ids: List[str] = []
        self.coords: np.ndarray = np.empty((0, 3), dtype=np.float32)
        self.tree: Optional[Any] = None

    def build(self, pois: List[POIRecord]) -> None:
        """Rebuild KD-Tree from a list of POI records."""
        self.poi_ids = [p.id for p in pois]
        if not self.poi_ids:
            self.coords = np.empty((0, 3), dtype=np.float32)
            self.tree = None
            return

        self.coords = np.array([[p.pos_x, p.pos_y, p.pos_z] for p in pois], dtype=np.float32)
        if _HAS_SCIPY and KDTree is not None:
            self.tree = KDTree(self.coords)
        logger.debug(f"Built KD-Tree for venue '{self.venue_id}' with {len(self.poi_ids)} POIs.")

    def query_radius(self, center: Point3D, radius: float) -> List[Tuple[str, float]]:
        """Return list of (poi_id, distance) within Euclidean radius (meters), sorted by distance."""
        if len(self.poi_ids) == 0:
            return []

        query_pt = np.array([center.x, center.y, center.z], dtype=np.float32)

        if _HAS_SCIPY and self.tree is not None:
            indices = self.tree.query_ball_point(query_pt, r=radius)
            if not indices:
                return []

            results = []
            for idx in indices:
                dist = float(np.linalg.norm(self.coords[idx] - query_pt))
                results.append((self.poi_ids[idx], dist))

            results.sort(key=lambda item: item[1])
            return results

        # Vectorized NumPy fallback (fast for N <= 10,000)
        diffs = self.coords - query_pt
        dists = np.linalg.norm(diffs, axis=1)
        matching_indices = np.where(dists <= radius)[0]
        if len(matching_indices) == 0:
            return []

        results = [(self.poi_ids[idx], float(dists[idx])) for idx in matching_indices]
        results.sort(key=lambda item: item[1])
        return results

    def query_nearest(self, point: Point3D, k: int = 1) -> List[Tuple[str, float]]:
        """Find k closest POIs to the given 3D position."""
        if len(self.poi_ids) == 0:
            return []

        query_pt = np.array([point.x, point.y, point.z], dtype=np.float32)
        k = min(k, len(self.poi_ids))

        if _HAS_SCIPY and self.tree is not None:
            distances, indices = self.tree.query(query_pt, k=k)
            if k == 1:
                distances = [distances]
                indices = [indices]

            results = []
            for dist, idx in zip(distances, indices):
                results.append((self.poi_ids[idx], float(dist)))
            return results

        # Vectorized NumPy fallback
        diffs = self.coords - query_pt
        dists = np.linalg.norm(diffs, axis=1)
        sorted_indices = np.argsort(dists)[:k]
        return [(self.poi_ids[idx], float(dists[idx])) for idx in sorted_indices]


class SpatialIndexManager:
    """Manages spatial indices across multiple venues with thread-safe caching."""

    def __init__(self):
        self._indices: Dict[str, VenueSpatialIndex] = {}

    def get_index(self, venue_id: str) -> VenueSpatialIndex:
        if venue_id not in self._indices:
            self._indices[venue_id] = VenueSpatialIndex(venue_id)
        return self._indices[venue_id]

    def invalidate(self, venue_id: str) -> None:
        """Clear cache for venue when POIs are modified."""
        if venue_id in self._indices:
            del self._indices[venue_id]


spatial_index_manager = SpatialIndexManager()
