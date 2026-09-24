from typing import Any, Dict, List, Tuple
import numpy as np

try:
    import scipy.ndimage
    _HAS_SCIPY = True
except ImportError:
    scipy = None
    _HAS_SCIPY = False

from app.algorithms.occupancy_grid import OccupancyGrid, STATE_WALKABLE


def _label_components_fallback(binary_walkable: np.ndarray) -> Tuple[np.ndarray, int, List[int]]:
    """8-connected component labeling fallback in pure Python/NumPy."""
    H, W = binary_walkable.shape
    labeled = np.zeros((H, W), dtype=np.int32)
    current_label = 0
    region_sizes = []
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    for r in range(H):
        for c in range(W):
            if binary_walkable[r, c] == 1 and labeled[r, c] == 0:
                current_label += 1
                count = 0
                stack = [(r, c)]
                labeled[r, c] = current_label
                while stack:
                    cr, cc = stack.pop()
                    count += 1
                    for dr, dc in neighbors:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < H and 0 <= nc < W:
                            if binary_walkable[nr, nc] == 1 and labeled[nr, nc] == 0:
                                labeled[nr, nc] = current_label
                                stack.append((nr, nc))
                region_sizes.append(count)
    return labeled, current_label, region_sizes


class RegionAnalysisReport:
    """Detailed diagnostic report on walkable surface continuity and disconnected regions."""

    def __init__(
        self,
        total_walkable_cells: int,
        total_walkable_area_m2: float,
        num_regions: int,
        regions: List[Dict[str, Any]],
        has_disconnected_regions: bool,
    ):
        self.total_walkable_cells = total_walkable_cells
        self.total_walkable_area_m2 = total_walkable_area_m2
        self.num_regions = num_regions
        self.regions = regions
        self.has_disconnected_regions = has_disconnected_regions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_walkable_cells": self.total_walkable_cells,
            "total_walkable_area_m2": round(self.total_walkable_area_m2, 2),
            "num_regions": self.num_regions,
            "has_disconnected_regions": self.has_disconnected_regions,
            "regions": self.regions,
        }


def analyze_walkable_regions(grid: OccupancyGrid) -> RegionAnalysisReport:
    """Identifies and measures disconnected walkable islands using connected component labeling."""
    binary_walkable = (grid.data == STATE_WALKABLE).astype(np.int32)
    cell_area = grid.cell_size * grid.cell_size
    total_cells = int(np.sum(binary_walkable))
    total_area = total_cells * cell_area

    if total_cells == 0:
        return RegionAnalysisReport(
            total_walkable_cells=0,
            total_walkable_area_m2=0.0,
            num_regions=0,
            regions=[],
            has_disconnected_regions=False,
        )

    if _HAS_SCIPY and scipy is not None:
        structure = np.ones((3, 3), dtype=np.int32)
        labeled_array, num_features = scipy.ndimage.label(binary_walkable, structure=structure)
        if num_features == 0:
            return RegionAnalysisReport(
                total_walkable_cells=0,
                total_walkable_area_m2=0.0,
                num_regions=0,
                regions=[],
                has_disconnected_regions=False,
            )
        raw_sizes = scipy.ndimage.sum(binary_walkable, labeled_array, range(1, num_features + 1))
        if not isinstance(raw_sizes, np.ndarray):
            raw_sizes = np.array([raw_sizes])
        region_sizes = [int(s) for s in raw_sizes]
    else:
        labeled_array, num_features, region_sizes = _label_components_fallback(binary_walkable)
        if num_features == 0:
            return RegionAnalysisReport(
                total_walkable_cells=0,
                total_walkable_area_m2=0.0,
                num_regions=0,
                regions=[],
                has_disconnected_regions=False,
            )

    regions_info = []
    for idx, count in enumerate(region_sizes, start=1):
        count_int = int(count)
        area_m2 = round(count_int * cell_area, 2)
        pct = round((count_int / total_cells) * 100.0, 1)

        # Find bounding box of this specific region
        rows, cols = np.where(labeled_array == idx)
        min_c, max_c = int(np.min(cols)), int(np.max(cols))
        min_r, max_r = int(np.min(rows)), int(np.max(rows))
        min_x, min_z = grid.grid_to_world(min_c, min_r)
        max_x, max_z = grid.grid_to_world(max_c, max_r)

        regions_info.append(
            {
                "region_id": idx,
                "cell_count": count_int,
                "area_m2": area_m2,
                "percentage_of_walkable": pct,
                "is_primary": False,
                "bounds": {
                    "min": {"x": min_x, "z": min_z},
                    "max": {"x": max_x, "z": max_z},
                },
            }
        )

    # Sort regions by size descending
    regions_info.sort(key=lambda r: r["cell_count"], reverse=True)
    if regions_info:
        regions_info[0]["is_primary"] = True

    has_disconnected = num_features > 1

    return RegionAnalysisReport(
        total_walkable_cells=total_cells,
        total_walkable_area_m2=total_area,
        num_regions=num_features,
        regions=regions_info,
        has_disconnected_regions=has_disconnected,
    )
