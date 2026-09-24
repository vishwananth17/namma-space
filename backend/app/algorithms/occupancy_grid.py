import math
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw

from app.models.common import BoundingBox, Point3D
from app.utils.logger import logger

# Cell State Constants
STATE_VOID = 0               # Outside room / unmapped space
STATE_WALKABLE = 1           # Traversable open floor
STATE_OBSTACLE = 2           # Rigid obstacle (wall, desk, column)
STATE_INFLATED = 3           # Clearance buffer around obstacles


class OccupancyGrid:
    """2D rasterized occupancy grid representation of an indoor venue for pathfinding."""

    def __init__(
        self,
        bounds: BoundingBox,
        cell_size: float = 0.15,
        floor_height: float = 0.0,
    ):
        self.bounds = bounds
        self.cell_size = float(cell_size)
        self.floor_height = float(floor_height)

        self.min_x = bounds.min.x
        self.max_x = bounds.max.x
        self.min_z = bounds.min.z
        self.max_z = bounds.max.z

        self.width_m = self.max_x - self.min_x
        self.height_m = self.max_z - self.min_z

        self.cols = int(math.ceil(self.width_m / self.cell_size))
        self.rows = int(math.ceil(self.height_m / self.cell_size))

        # Initialize full grid as VOID
        self.data: np.ndarray = np.full((self.rows, self.cols), STATE_VOID, dtype=np.int8)

    def world_to_grid(self, x: float, z: float) -> Tuple[int, int]:
        """Convert world coordinates (x, z) to grid indices (col, row)."""
        col = int((x - self.min_x) / self.cell_size)
        row = int((z - self.min_z) / self.cell_size)
        return col, row

    def grid_to_world(self, col: int, row: int) -> Tuple[float, float]:
        """Convert grid cell (col, row) center back to world coordinates (x, z)."""
        x = self.min_x + (col + 0.5) * self.cell_size
        z = self.min_z + (row + 0.5) * self.cell_size
        return round(x, 3), round(z, 3)

    def in_bounds(self, col: int, row: int) -> bool:
        """Check if grid cell lies within grid dimensions."""
        return 0 <= col < self.cols and 0 <= row < self.rows

    def is_walkable(self, col: int, row: int) -> bool:
        """A cell is traversable only if marked strictly as STATE_WALKABLE."""
        if not self.in_bounds(col, row):
            return False
        return bool(self.data[row, col] == STATE_WALKABLE)

    def mark_floor_walkable(self, margin_m: float = 0.0) -> None:
        """Mark the rectangular bounds of the floor area as walkable."""
        col_start = int(margin_m / self.cell_size)
        col_end = self.cols - col_start
        row_start = int(margin_m / self.cell_size)
        row_end = self.rows - row_start

        col_start = max(0, col_start)
        col_end = min(self.cols, col_end)
        row_start = max(0, row_start)
        row_end = min(self.rows, row_end)

        self.data[row_start:row_end, col_start:col_end] = STATE_WALKABLE

    def set_obstacle_box(
        self, min_x: float, max_x: float, min_z: float, max_z: float
    ) -> None:
        """Mark an axis-aligned bounding box obstacle (e.g. wall, table) as STATE_OBSTACLE."""
        c1, r1 = self.world_to_grid(min_x, min_z)
        c2, r2 = self.world_to_grid(max_x, max_z)

        col_min = max(0, min(c1, c2))
        col_max = min(self.cols - 1, max(c1, c2))
        row_min = max(0, min(r1, r2))
        row_max = min(self.rows - 1, max(r1, r2))

        self.data[row_min : row_max + 1, col_min : col_max + 1] = STATE_OBSTACLE

    def inflate_obstacles(self, agent_radius_m: float = 0.3) -> None:
        """Inflate obstacles by agent radius using circular Euclidean kernel.
        
        Cells within agent radius of an obstacle are set to STATE_INFLATED
        if they were previously STATE_WALKABLE.
        """
        radius_cells = int(math.ceil(agent_radius_m / self.cell_size))
        if radius_cells <= 0:
            return

        # Precompute circular relative offsets
        offsets = []
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                dist = math.sqrt((dr * self.cell_size) ** 2 + (dc * self.cell_size) ** 2)
                if 0 < dist <= agent_radius_m:
                    offsets.append((dr, dc))

        # Find all rigid obstacle cells
        obstacle_rows, obstacle_cols = np.where(self.data == STATE_OBSTACLE)

        for r_obs, c_obs in zip(obstacle_rows, obstacle_cols):
            for dr, dc in offsets:
                nr, nc = r_obs + dr, c_obs + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    if self.data[nr, nc] == STATE_WALKABLE:
                        self.data[nr, nc] = STATE_INFLATED

    def save(self, file_path: Path) -> None:
        """Save grid and spatial metadata to compressed .npz archive."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            file_path,
            data=self.data,
            cell_size=self.cell_size,
            floor_height=self.floor_height,
            min_x=self.min_x,
            max_x=self.max_x,
            min_z=self.min_z,
            max_z=self.max_z,
        )
        logger.info(f"Saved occupancy grid ({self.cols}x{self.rows}) to: {file_path}")

    @classmethod
    def load(cls, file_path: Path) -> "OccupancyGrid":
        """Load grid from .npz archive."""
        npz = np.load(file_path)
        min_pt = Point3D(x=float(npz["min_x"]), y=0.0, z=float(npz["min_z"]))
        max_pt = Point3D(x=float(npz["max_x"]), y=3.0, z=float(npz["max_z"]))
        bounds = BoundingBox.from_min_max(min_pt, max_pt)
        grid_obj = cls(
            bounds=bounds,
            cell_size=float(npz["cell_size"]),
            floor_height=float(npz["floor_height"]),
        )
        grid_obj.data = npz["data"]
        return grid_obj

    def render_debug_image(
        self,
        output_path: Path,
        path_world_coords: Optional[List[Point3D]] = None,
        scale: int = 4,
    ) -> None:
        """Generate a high-contrast top-down debug PNG map of walkable space and obstacles."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Dimensions
        img_w = self.cols * scale
        img_h = self.rows * scale

        # Color palette
        COLOR_VOID = (38, 50, 56)          # Dark Slate
        COLOR_WALKABLE = (245, 245, 250)   # Clean Off-White
        COLOR_OBSTACLE = (33, 33, 33)      # Solid Black / Dark Charcoal
        COLOR_INFLATED = (255, 171, 145)   # Light Salmon / Buffer clearance

        # Build RGB array
        rgb = np.zeros((self.rows, self.cols, 3), dtype=np.uint8)
        rgb[self.data == STATE_VOID] = COLOR_VOID
        rgb[self.data == STATE_WALKABLE] = COLOR_WALKABLE
        rgb[self.data == STATE_OBSTACLE] = COLOR_OBSTACLE
        rgb[self.data == STATE_INFLATED] = COLOR_INFLATED

        img = Image.fromarray(rgb, mode="RGB")
        # Scale up using nearest-neighbor for crisp grid cells
        img = img.resize((img_w, img_h), Image.Resampling.NEAREST)

        # Draw path overlay if supplied
        if path_world_coords and len(path_world_coords) > 1:
            draw = ImageDraw.Draw(img)
            pixel_points = []
            for pt in path_world_coords:
                col, row = self.world_to_grid(pt.x, pt.z)
                px = (col + 0.5) * scale
                py = (row + 0.5) * scale
                pixel_points.append((px, py))

            # Draw thick path line
            draw.line(pixel_points, fill=(2, 136, 209), width=max(2, int(scale * 0.8)))

            # Start circle (Green)
            sx, sy = pixel_points[0]
            r = scale * 1.5
            draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(76, 175, 80), outline=(255, 255, 255))

            # Goal circle (Red)
            gx, gy = pixel_points[-1]
            draw.ellipse((gx - r, gy - r, gx + r, gy + r), fill=(244, 67, 54), outline=(255, 255, 255))

        img.save(output_path, format="PNG")
        logger.info(f"Rendered debug navigation map to: {output_path}")
