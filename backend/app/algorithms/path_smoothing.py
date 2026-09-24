import math
from typing import List, Tuple

from app.algorithms.occupancy_grid import OccupancyGrid


def has_line_of_sight(
    grid: OccupancyGrid,
    col1: int,
    row1: int,
    col2: int,
    row2: int,
    step_samples: int = 0,
) -> bool:
    """Raycast between two cells on the occupancy grid to verify uninterrupted clearance."""
    if not grid.is_walkable(col1, row1) or not grid.is_walkable(col2, row2):
        return False

    dx = col2 - col1
    dr = row2 - row1
    dist = math.hypot(dx, dr)
    if dist < 1.0:
        return True

    # Sample along line with sub-cell step size (e.g. 0.5 cells)
    if step_samples <= 0:
        step_samples = max(2, int(dist * 2.5))

    for step in range(1, step_samples):
        t = step / float(step_samples)
        sample_c = int(round(col1 + t * dx))
        sample_r = int(round(row1 + t * dr))
        if not grid.is_walkable(sample_c, sample_r):
            return False

    return True


def smooth_path(
    grid: OccupancyGrid,
    grid_path: List[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    """Greedy string-pulling algorithm to eliminate zig-zag grid artifacts.
    
    Bypasses intermediate waypoints whenever direct line of sight exists.
    Reduces 50+ grid steps to 3-6 natural straight segments.
    """
    if len(grid_path) <= 2:
        return grid_path

    smoothed = [grid_path[0]]
    curr_idx = 0
    n = len(grid_path)

    while curr_idx < n - 1:
        # Search backwards from the end to find the furthest reachable waypoint
        furthest = curr_idx + 1
        for lookahead in range(n - 1, curr_idx, -1):
            c1, r1 = grid_path[curr_idx]
            c2, r2 = grid_path[lookahead]
            if has_line_of_sight(grid, c1, r1, c2, r2):
                furthest = lookahead
                break

        smoothed.append(grid_path[furthest])
        curr_idx = furthest

    return smoothed
