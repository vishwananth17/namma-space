from pathlib import Path
from typing import Optional
import numpy as np

try:
    import trimesh
    _HAS_TRIMESH = True
except ImportError:
    trimesh = None
    _HAS_TRIMESH = False

from app.algorithms.occupancy_grid import OccupancyGrid, STATE_OBSTACLE, STATE_WALKABLE
from app.models.venue import VenueMetadata
from app.utils.logger import logger


def generate_occupancy_grid_from_mesh(
    venue: VenueMetadata,
    model_file_path: Path,
    cell_size: float = 0.15,
    agent_radius: float = 0.3,
    slice_height_min: float = 0.2,
    slice_height_max: float = 1.8,
) -> OccupancyGrid:
    """Slices a 3D mesh at a configurable height band to extract an obstacle-aware 2D occupancy grid."""
    logger.info(
        f"Generating occupancy grid for venue '{venue.id}' from {model_file_path} "
        f"(cell_size={cell_size}m, agent_radius={agent_radius}m)"
    )

    grid = OccupancyGrid(
        bounds=venue.bounds,
        cell_size=cell_size,
        floor_height=venue.floor_height,
    )

    # 1. Mark interior floor as walkable (leaving outer 0.2m for exterior walls)
    grid.mark_floor_walkable(margin_m=0.2)

    # 2. Mark perimeter room boundaries as solid obstacles
    grid.set_obstacle_box(venue.bounds.min.x, venue.bounds.max.x, venue.bounds.min.z, venue.bounds.min.z + 0.2)
    grid.set_obstacle_box(venue.bounds.min.x, venue.bounds.max.x, venue.bounds.max.z - 0.2, venue.bounds.max.z)
    grid.set_obstacle_box(venue.bounds.min.x, venue.bounds.min.x + 0.2, venue.bounds.min.z, venue.bounds.max.z)
    grid.set_obstacle_box(venue.bounds.max.x - 0.2, venue.bounds.max.x, venue.bounds.min.z, venue.bounds.max.z)

    # 3. Load 3D model using Trimesh (if available and file exists)
    if model_file_path.exists() and _HAS_TRIMESH and trimesh is not None:
        try:
            loaded = trimesh.load(model_file_path)
            if isinstance(loaded, trimesh.Scene):
                geometries = list(loaded.geometry.values())
            else:
                geometries = [loaded]

            y_low = venue.floor_height + slice_height_min
            y_high = venue.floor_height + slice_height_max

            for geom in geometries:
                if not hasattr(geom, "vertices") or len(geom.vertices) == 0:
                    continue

                gb = geom.bounds
                if gb is not None and len(gb) == 2:
                    # Check if geometry intersects the obstacle height band
                    if gb[1][1] >= y_low and gb[0][1] <= y_high:
                        # Check if it is not the main floor plane
                        is_floor = (
                            (gb[1][0] - gb[0][0]) >= (venue.bounds.dimensions.x - 0.5)
                            and (gb[1][2] - gb[0][2]) >= (venue.bounds.dimensions.z - 0.5)
                        )
                        if not is_floor:
                            grid.set_obstacle_box(gb[0][0], gb[1][0], gb[0][2], gb[1][2])

                # Filter vertices within the slice height band for irregular shapes
                v = geom.vertices
                in_slice_mask = (v[:, 1] >= y_low) & (v[:, 1] <= y_high)
                slice_vertices = v[in_slice_mask]

                if len(slice_vertices) > 0:
                    # Map slice vertices to grid cells
                    for pt in slice_vertices:
                        c, r = grid.world_to_grid(pt[0], pt[2])
                        if grid.in_bounds(c, r):
                            grid.data[r, c] = STATE_OBSTACLE

            logger.info(f"Successfully processed 3D geometry for venue '{venue.id}'.")
        except Exception as e:
            logger.error(f"Error slicing mesh from {model_file_path}: {e}", exc_info=True)

    # 4. Fallback / Configuration overrides from config or overrides.json
    overrides = venue.config.get("overrides", {})
    venue_dir = model_file_path.parent.parent
    overrides_file = venue_dir / "overrides.json"
    if overrides_file.exists():
        try:
            import json
            with open(overrides_file, "r", encoding="utf-8") as f:
                file_overrides = json.load(f)
                overrides.update(file_overrides)
            logger.info(f"Loaded manual overrides from {overrides_file}")
        except Exception as e:
            logger.error(f"Error loading {overrides_file}: {e}")

    # A. Add obstacles (boxes)
    for obs in overrides.get("add_obstacles", []) + venue.config.get("custom", {}).get("manual_obstacles", []):
        grid.set_obstacle_box(
            min_x=obs["min"]["x"],
            max_x=obs["max"]["x"],
            min_z=obs["min"]["z"],
            max_z=obs["max"]["z"],
        )

    # B. Add walkable / remove obstacle (boxes)
    for w in overrides.get("add_walkable", []) + overrides.get("remove_obstacles", []):
        c1, r1 = grid.world_to_grid(w["min"]["x"], w["min"]["z"])
        c2, r2 = grid.world_to_grid(w["max"]["x"], w["max"]["z"])
        col_min, col_max = max(0, min(c1, c2)), min(grid.cols - 1, max(c1, c2))
        row_min, row_max = max(0, min(r1, r2)), min(grid.rows - 1, max(r1, r2))
        grid.data[row_min : row_max + 1, col_min : col_max + 1] = STATE_WALKABLE

    # C. Remove walkable (mark void)
    for rw in overrides.get("remove_walkable", []):
        c1, r1 = grid.world_to_grid(rw["min"]["x"], rw["min"]["z"])
        c2, r2 = grid.world_to_grid(rw["max"]["x"], rw["max"]["z"])
        col_min, col_max = max(0, min(c1, c2)), min(grid.cols - 1, max(c1, c2))
        row_min, row_max = max(0, min(r1, r2)), min(grid.rows - 1, max(r1, r2))
        grid.data[row_min : row_max + 1, col_min : col_max + 1] = 0

    # 5. Inflate obstacles by agent radius
    grid.inflate_obstacles(agent_radius_m=agent_radius)

    return grid
