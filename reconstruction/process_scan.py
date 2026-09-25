"""3D Reconstruction & Spatial Scan Ingestion Pipeline.
Processes raw 3D scans (OBJ, PLY, GLTF, STL) into optimized GLB models
and automatically registers them with the NammaSpace spatial backend.

Usage:
    python reconstruction/process_scan.py --input scan.obj --venue-id custom_hall --venue-name "Custom Hall"
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import trimesh
from scripts.onboard_venue import onboard_venue


def process_and_onboard_scan(
    input_file: Path,
    venue_id: str,
    venue_name: str,
    grid_resolution: float = 0.15,
    agent_radius: float = 0.30,
) -> bool:
    """Load raw scan file, export clean GLB, and invoke zero-hardcode onboarding."""
    print(f"\n=======================================================")
    print(f"  NammaSpace 3D Scan Ingestion Pipeline")
    print(f"=======================================================")
    print(f"Input scan: {input_file}")
    print(f"Target Venue ID: {venue_id}")

    if not input_file.exists():
        print(f"Error: Input file '{input_file}' does not exist.")
        return False

    # 1. Prepare target venue directory
    venue_dir = backend_dir / "data" / "venues" / venue_id
    models_dir = venue_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    glb_target = models_dir / "scene.glb"

    # 2. Ingest with trimesh and export optimized GLB
    print(f"\n[1/3] Loading 3D scan geometry...")
    try:
        scene_or_mesh = trimesh.load(str(input_file))
        print(f"Successfully loaded '{input_file.name}'")
    except Exception as e:
        print(f"Failed to load scan file: {e}")
        return False

    print(f"\n[2/3] Exporting optimized binary GLB to {glb_target}...")
    try:
        if isinstance(scene_or_mesh, trimesh.Trimesh):
            scene = trimesh.Scene(scene_or_mesh)
        else:
            scene = scene_or_mesh
        scene.export(str(glb_target), file_type="glb")
        print(f"GLB export successful ({glb_target.stat().st_size / 1024:.1f} KB)")
    except Exception as e:
        print(f"Failed to export GLB: {e}")
        return False

    # 3. Trigger onboard_venue
    print(f"\n[3/3] Generating 2D occupancy grid, obstacle inflation, and spatial bounds...")
    try:
        onboard_venue(
            venue_id=venue_id,
            venue_name=venue_name,
            model_path=glb_target,
            grid_resolution=grid_resolution,
            agent_radius=agent_radius,
        )
        print(f"\n[SUCCESS] Venue '{venue_id}' successfully ingested and onboarded!")
        print(f"Restart or hot-reload backend to explore in 3D viewer.")
        return True
    except Exception as e:
        print(f"Onboarding failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ingest raw 3D scans into NammaSpace.")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to input scan (.obj, .ply, .gltf, .stl)")
    parser.add_argument("--venue-id", "-id", type=str, required=True, help="Unique venue ID (e.g. iitb_lab)")
    parser.add_argument("--venue-name", "-n", type=str, required=True, help="Human-readable venue name")
    parser.add_argument("--resolution", "-r", type=float, default=0.15, help="Grid cell size in meters (default 0.15m)")
    parser.add_argument("--agent-radius", "-a", type=float, default=0.30, help="Obstacle clearance buffer in meters (default 0.30m)")

    args = parser.parse_args()
    success = process_and_onboard_scan(
        input_file=args.input,
        venue_id=args.venue_id,
        venue_name=args.venue_name,
        grid_resolution=args.resolution,
        agent_radius=args.agent_radius,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
