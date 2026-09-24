from typing import Any, Dict, List
import numpy as np
import scipy.ndimage

from app.algorithms.occupancy_grid import OccupancyGrid, STATE_WALKABLE


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
    # 8-connected structuring element for adjacency
    structure = np.ones((3, 3), dtype=np.int32)
    binary_walkable = (grid.data == STATE_WALKABLE).astype(np.int32)

    labeled_array, num_features = scipy.ndimage.label(binary_walkable, structure=structure)
    cell_area = grid.cell_size * grid.cell_size

    total_cells = int(np.sum(binary_walkable))
    total_area = total_cells * cell_area

    if num_features == 0 or total_cells == 0:
        return RegionAnalysisReport(
            total_walkable_cells=0,
            total_walkable_area_m2=0.0,
            num_regions=0,
            regions=[],
            has_disconnected_regions=False,
        )

    # Measure sizes of each labeled component
    region_sizes = scipy.ndimage.sum(binary_walkable, labeled_array, range(1, num_features + 1))
    if not isinstance(region_sizes, np.ndarray):
        region_sizes = np.array([region_sizes])

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
