import math
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from sqlalchemy.orm import Session

from app.algorithms.astar import AStarPathfinder, NoPathFoundError, NoWalkableCellError
from app.algorithms.mesh_slicer import generate_occupancy_grid_from_mesh
from app.algorithms.occupancy_grid import (
    OccupancyGrid,
    STATE_INFLATED,
    STATE_OBSTACLE,
    STATE_WALKABLE,
)
from app.algorithms.path_smoothing import smooth_path
from app.config import settings
from app.models.common import Point3D
from app.models.navigation import (
    NavMeshDebugInfo,
    NavigationRequest,
    NavigationResponse,
)
from app.services.poi_service import POINotFoundError, poi_service
from app.services.venue_service import VenueNotFoundError, venue_service
from app.utils.logger import logger


class NavigationService:
    """Orchestrates mesh slicing, grid caching, A* pathfinding, and line-of-sight path smoothing."""

    def __init__(self):
        self._grids: Dict[str, OccupancyGrid] = {}

    def get_or_build_grid(self, venue_id: str, force_rebuild: bool = False) -> OccupancyGrid:
        """Fetch cached occupancy grid from memory or disk, or generate from 3D model."""
        if not force_rebuild and venue_id in self._grids:
            return self._grids[venue_id]

        venue = venue_service.get_venue(venue_id)
        venue_dir = venue_service.get_venue_dir(venue_id)
        grid_file = venue_dir / "navmesh.npz"
        debug_img_file = venue_dir / "debug_map.png"

        # Check if saved grid exists on disk
        if not force_rebuild and grid_file.exists():
            try:
                grid = OccupancyGrid.load(grid_file)
                self._grids[venue_id] = grid
                logger.info(f"Loaded existing occupancy grid for venue '{venue_id}' from disk.")
                if not debug_img_file.exists():
                    grid.render_debug_image(debug_img_file)
                return grid
            except Exception as e:
                logger.warning(f"Could not load grid from {grid_file} ({e}). Rebuilding...")

        # Build grid from 3D mesh model
        model_path = venue_dir / venue.model_filename
        custom_cfg = venue.config.get("custom", {})
        cell_size = float(custom_cfg.get("grid_resolution", 0.15))
        agent_radius = float(custom_cfg.get("agent_radius", 0.3))

        grid = generate_occupancy_grid_from_mesh(
            venue=venue,
            model_file_path=model_path,
            cell_size=cell_size,
            agent_radius=agent_radius,
        )

        # Save to disk
        grid.save(grid_file)
        grid.render_debug_image(debug_img_file)
        self._grids[venue_id] = grid
        return grid

    def resolve_location(
        self,
        db: Session,
        venue_id: str,
        loc: Union[Point3D, str, None],
        poi_id_alias: Optional[str] = None,
        pos_alias: Optional[Point3D] = None,
    ) -> Tuple[Point3D, str]:
        """Resolves input location into (Point3D, display_name)."""
        # 1. Direct Point3D alias
        if pos_alias is not None:
            return pos_alias, f"Custom Coordinate ({pos_alias.x}, {pos_alias.z})"

        # 2. POI ID alias
        if poi_id_alias is not None:
            poi = poi_service.get_poi(db, venue_id, poi_id_alias)
            return poi.position, poi.name

        # 3. Union field 'start' / 'goal'
        if isinstance(loc, Point3D):
            return loc, f"Coordinate ({loc.x}, {loc.z})"
        elif isinstance(loc, str):
            poi = poi_service.get_poi(db, venue_id, loc)
            return poi.position, poi.name
        elif isinstance(loc, dict):
            pt = Point3D(**loc)
            return pt, f"Coordinate ({pt.x}, {pt.z})"

        raise ValueError("Location must specify either a valid POI id string or Point3D coordinates.")

    def navigate(
        self,
        db: Session,
        venue_id: str,
        request: NavigationRequest,
    ) -> NavigationResponse:
        """Computes obstacle-aware path from origin to destination using A* with path smoothing."""
        start_time = time.perf_counter()
        venue = venue_service.get_venue(venue_id)

        # 1. Resolve start and goal
        origin_pt, origin_name = self.resolve_location(
            db, venue_id, request.start, request.from_poi_id, request.from_position
        )
        goal_pt, goal_name = self.resolve_location(
            db, venue_id, request.goal, request.to_poi_id, request.to_position
        )

        # 2. Get occupancy grid
        grid = self.get_or_build_grid(venue_id)

        # 3. Execute A* pathfinding
        pathfinder = AStarPathfinder(grid)
        raw_grid_path, start_snapped, goal_snapped = pathfinder.find_path(
            start_world=(origin_pt.x, origin_pt.z),
            goal_world=(goal_pt.x, goal_pt.z),
            snap=True,
        )

        # 4. Path smoothing (string pulling)
        if request.smooth_path and len(raw_grid_path) > 2:
            processed_grid_path = smooth_path(grid, raw_grid_path)
            path_smoothed = True
        else:
            processed_grid_path = raw_grid_path
            path_smoothed = False

        # 5. Convert grid waypoints to 3D world coordinates
        floor_y = venue.floor_height + 0.1  # slightly above floor plane for rendering
        waypoints_3d: List[Point3D] = []

        # Always start at exact origin point
        waypoints_3d.append(Point3D(x=origin_pt.x, y=floor_y, z=origin_pt.z))

        for c, r in processed_grid_path:
            wx, wz = grid.grid_to_world(c, r)
            # Avoid repeating nearly identical point
            if len(waypoints_3d) > 0:
                last = waypoints_3d[-1]
                if abs(last.x - wx) < 0.05 and abs(last.z - wz) < 0.05:
                    continue
            waypoints_3d.append(Point3D(x=wx, y=floor_y, z=wz))

        # Always terminate at exact destination point
        if len(waypoints_3d) == 0 or (
            abs(waypoints_3d[-1].x - goal_pt.x) > 0.05 or abs(waypoints_3d[-1].z - goal_pt.z) > 0.05
        ):
            waypoints_3d.append(Point3D(x=goal_pt.x, y=floor_y, z=goal_pt.z))

        # 6. Calculate total length and estimated walking time
        total_dist = 0.0
        for i in range(len(waypoints_3d) - 1):
            p1 = waypoints_3d[i]
            p2 = waypoints_3d[i + 1]
            total_dist += math.hypot(p2.x - p1.x, p2.z - p1.z)

        total_dist = round(total_dist, 2)
        walking_time = round(total_dist / 1.2, 1)  # 1.2 m/s standard indoor speed
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return NavigationResponse(
            venue_id=venue_id,
            origin_name=origin_name,
            destination_name=goal_name,
            origin_snapped=start_snapped,
            destination_snapped=goal_snapped,
            waypoints=waypoints_3d,
            total_waypoints=len(waypoints_3d),
            total_distance_meters=total_dist,
            estimated_walking_time_seconds=walking_time,
            execution_time_ms=elapsed_ms,
            path_smoothed=path_smoothed,
        )

    def get_debug_info(self, venue_id: str) -> NavMeshDebugInfo:
        """Returns statistics on walkable cells, obstacle cells, and map visualization URL."""
        grid = self.get_or_build_grid(venue_id)
        walkable_cnt = int(np.sum(grid.data == STATE_WALKABLE))
        obstacle_cnt = int(np.sum(grid.data == STATE_OBSTACLE))
        inflated_cnt = int(np.sum(grid.data == STATE_INFLATED))
        total_valid = walkable_cnt + obstacle_cnt + inflated_cnt
        pct = round((walkable_cnt / total_valid * 100.0), 1) if total_valid > 0 else 0.0

        return NavMeshDebugInfo(
            venue_id=venue_id,
            grid_width=grid.cols,
            grid_height=grid.rows,
            cell_size=grid.cell_size,
            walkable_cells_count=walkable_cnt,
            obstacle_cells_count=obstacle_cnt,
            inflated_cells_count=inflated_cnt,
            walkable_percentage=pct,
            debug_map_url=f"/venues/{venue_id}/navmesh/debug.png",
        )

    def get_debug_image_path(self, venue_id: str) -> Path:
        venue_dir = venue_service.get_venue_dir(venue_id)
        img_path = venue_dir / "debug_map.png"
        if not img_path.exists():
            grid = self.get_or_build_grid(venue_id)
            grid.render_debug_image(img_path)
        return img_path


navigation_service = NavigationService()
