"""Generates a synthetic 3D indoor room (.glb) for testing and development.

Creates a 20m x 15m indoor space with a floor, perimeter walls,
and internal obstacle boxes (workstations/pillars).
"""

from pathlib import Path
import trimesh
import numpy as np


def create_synthetic_room(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    geometries = []

    # 1. Floor: 20m (X) x 15m (Z), thickness 0.1m, centered at Y=-0.05
    floor = trimesh.creation.box(extents=[20.0, 0.1, 15.0])
    floor.apply_translation([0.0, -0.05, 0.0])
    floor.visual.vertex_colors = [200, 205, 210, 255]  # Light gray floor
    geometries.append(floor)

    # 2. North & South Walls: along X, Z at +-7.5m, height 3m
    wall_north = trimesh.creation.box(extents=[20.0, 3.0, 0.2])
    wall_north.apply_translation([0.0, 1.5, -7.5])
    wall_north.visual.vertex_colors = [230, 230, 235, 255]
    geometries.append(wall_north)

    wall_south = trimesh.creation.box(extents=[20.0, 3.0, 0.2])
    wall_south.apply_translation([0.0, 1.5, 7.5])
    wall_south.visual.vertex_colors = [230, 230, 235, 255]
    geometries.append(wall_south)

    # 3. East & West Walls: along Z, X at +-10.0m, height 3m
    wall_west = trimesh.creation.box(extents=[0.2, 3.0, 15.0])
    wall_west.apply_translation([-10.0, 1.5, 0.0])
    wall_west.visual.vertex_colors = [220, 225, 230, 255]
    geometries.append(wall_west)

    wall_east = trimesh.creation.box(extents=[0.2, 3.0, 15.0])
    wall_east.apply_translation([10.0, 1.5, 0.0])
    wall_east.visual.vertex_colors = [220, 225, 230, 255]
    geometries.append(wall_east)

    # 4. Interior obstacles (Workstations, Robotics Pen, Partitions)
    # Workstation Cluster A (West side)
    desk1 = trimesh.creation.box(extents=[3.0, 0.8, 1.5])
    desk1.apply_translation([-5.0, 0.4, -3.0])
    desk1.visual.vertex_colors = [120, 140, 160, 255]
    geometries.append(desk1)

    desk2 = trimesh.creation.box(extents=[3.0, 0.8, 1.5])
    desk2.apply_translation([-5.0, 0.4, 3.0])
    desk2.visual.vertex_colors = [120, 140, 160, 255]
    geometries.append(desk2)

    # Central Robotics Arena Barrier (Center-East)
    arena = trimesh.creation.box(extents=[4.0, 0.6, 4.0])
    arena.apply_translation([4.0, 0.3, 0.0])
    arena.visual.vertex_colors = [240, 160, 80, 255]
    geometries.append(arena)

    # Central Support Column
    column = trimesh.creation.box(extents=[0.8, 3.0, 0.8])
    column.apply_translation([0.0, 1.5, -2.0])
    column.visual.vertex_colors = [100, 100, 110, 255]
    geometries.append(column)

    # Combine into a single scene
    scene = trimesh.Scene(geometries)

    # Export to GLB
    glb_data = scene.export(file_type="glb")
    with open(output_path, "wb") as f:
        f.write(glb_data)

    print(f"Generated synthetic GLB room at: {output_path} ({len(glb_data)} bytes)")


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "data" / "venues" / "sample_lab" / "models" / "sample_room.glb"
    create_synthetic_room(target)
