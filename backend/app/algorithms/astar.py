import heapq
import math
from typing import List, Optional, Set, Tuple

from app.algorithms.occupancy_grid import OccupancyGrid


class PathfindingError(Exception):
    """Base exception for pathfinding failures."""
    pass


class NoWalkableCellError(PathfindingError):
    """Raised when start or goal cannot be snapped to any walkable grid cell."""
    pass


class NoPathFoundError(PathfindingError):
    """Raised when start and goal are disconnected by impassable obstacles."""
    pass


# 8-Direction Movements (d_col, d_row, base_step_cost)
SQRT2 = math.sqrt(2.0)
DIRECTIONS = [
    # Orthogonal
    (1, 0, 1.0),
    (-1, 0, 1.0),
    (0, 1, 1.0),
    (0, -1, 1.0),
    # Diagonal
    (1, 1, SQRT2),
    (1, -1, SQRT2),
    (-1, 1, SQRT2),
    (-1, -1, SQRT2),
]


def octile_heuristic(c1: int, r1: int, c2: int, r2: int, cell_size: float) -> float:
    """Admissible and consistent Octile heuristic for 8-connected grid navigation."""
    dx = abs(c1 - c2)
    dr = abs(r1 - r2)
    straight = abs(dx - dr)
    diagonal = min(dx, dr)
    return (straight + SQRT2 * diagonal) * cell_size


def snap_to_walkable(
    grid: OccupancyGrid,
    col: int,
    row: int,
    max_search_radius_m: float = 1.5,
) -> Tuple[int, int]:
    """Snap a coordinate to the nearest walkable cell using expanding concentric search.
    
    Returns (snapped_col, snapped_row) or raises NoWalkableCellError if none within radius.
    """
    if grid.is_walkable(col, row):
        return col, row

    max_r_cells = int(math.ceil(max_search_radius_m / grid.cell_size))
    best_cell = None
    best_dist = float("inf")

    for r in range(1, max_r_cells + 1):
        for dc in range(-r, r + 1):
            for dr in range(-r, r + 1):
                # Inspect perimeter of square ring
                if abs(dc) == r or abs(dr) == r:
                    nc, nr = col + dc, row + dr
                    if grid.is_walkable(nc, nr):
                        dist = math.sqrt(dc * dc + dr * dr)
                        if dist < best_dist:
                            best_dist = dist
                            best_cell = (nc, nr)
        if best_cell is not None:
            return best_cell

    raise NoWalkableCellError(
        f"Position at grid ({col}, {row}) is blocked and has no walkable cell within {max_search_radius_m}m."
    )


class AStarPathfinder:
    """8-connected obstacle-aware A* pathfinder preventing diagonal corner cutting."""

    def __init__(self, grid: OccupancyGrid):
        self.grid = grid

    def find_path(
        self,
        start_world: Tuple[float, float],
        goal_world: Tuple[float, float],
        snap: bool = True,
    ) -> Tuple[List[Tuple[int, int]], bool, bool]:
        """Find optimal 8-connected grid path from start to goal.
        
        Returns:
            (grid_path, start_was_snapped, goal_was_snapped)
        """
        sc, sr = self.grid.world_to_grid(start_world[0], start_world[1])
        gc, gr = self.grid.world_to_grid(goal_world[0], goal_world[1])

        start_snapped = False
        goal_snapped = False

        if not self.grid.is_walkable(sc, sr):
            if not snap:
                raise NoWalkableCellError(f"Start point ({start_world[0]}, {start_world[1]}) is not walkable.")
            sc, sr = snap_to_walkable(self.grid, sc, sr)
            start_snapped = True

        if not self.grid.is_walkable(gc, gr):
            if not snap:
                raise NoWalkableCellError(f"Goal point ({goal_world[0]}, {goal_world[1]}) is not walkable.")
            gc, gr = snap_to_walkable(self.grid, gc, gr)
            goal_snapped = True

        if (sc, sr) == (gc, gr):
            return [(sc, sr)], start_snapped, goal_snapped

        # A* Priority Queue: (f_score, counter, (col, row))
        counter = 0
        h_start = octile_heuristic(sc, sr, gc, gr, self.grid.cell_size)
        open_heap = [(h_start, counter, (sc, sr))]
        open_set_hash = {(sc, sr)}

        came_from = {}
        g_score = {(sc, sr): 0.0}

        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            open_set_hash.discard(current)

            curr_c, curr_r = current

            # Reached Goal
            if current == (gc, gr):
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path, start_snapped, goal_snapped

            curr_g = g_score[current]

            for dc, dr, step_mult in DIRECTIONS:
                neighbor_c = curr_c + dc
                neighbor_r = curr_r + dr

                # Check bounds and walkability
                if not self.grid.is_walkable(neighbor_c, neighbor_r):
                    continue

                # CRITICAL RULE: Prevent diagonal corner-cutting!
                # If moving diagonally, both adjacent orthogonal cells MUST be walkable!
                if dc != 0 and dr != 0:
                    adj1_walkable = self.grid.is_walkable(curr_c + dc, curr_r)
                    adj2_walkable = self.grid.is_walkable(curr_c, curr_r + dr)
                    if not (adj1_walkable and adj2_walkable):
                        # Blocked corner cut!
                        continue

                tentative_g = curr_g + (step_mult * self.grid.cell_size)
                neighbor = (neighbor_c, neighbor_r)

                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    h = octile_heuristic(neighbor_c, neighbor_r, gc, gr, self.grid.cell_size)
                    f = tentative_g + h

                    if neighbor not in open_set_hash:
                        counter += 1
                        heapq.heappush(open_heap, (f, counter, neighbor))
                        open_set_hash.add(neighbor)

        raise NoPathFoundError(
            f"No path exists between ({start_world[0]}, {start_world[1]}) and ({goal_world[0]}, {goal_world[1]}). "
            "Obstacles completely block traversal."
        )
