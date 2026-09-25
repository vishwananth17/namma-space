"""Single-command venue onboarding pipeline for Round 3 live venue evaluation.

Usage:
    python scripts/onboard_venue.py --model path/to/model.glb --venue-id iitb-hall --config config.json
    python scripts/onboard_venue.py --model path/to/model.glb --venue-id iitb-hall --pois seed_pois.json
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
import trimesh

# Ensure backend root is on Python path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.algorithms.mesh_slicer import generate_occupancy_grid_from_mesh
from app.algorithms.region_analyzer import analyze_walkable_regions
from app.config import settings
from app.db.session import SessionLocal, init_db
from app.models.common import BoundingBox, Point3D
from app.models.venue import SpawnPoint, VenueMetadata
from app.services.poi_service import poi_service
from app.services.venue_service import venue_service


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automated onboarding pipeline for new 3D indoor venues."
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to 3D model file (.glb, .gltf, .ply, or .obj)",
    )
    parser.add_argument(
        "--venue-id",
        type=str,
        required=True,
        help="Unique identifier for the new venue (e.g. 'iitb-hall')",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Human readable venue name (defaults to title-cased venue ID)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to custom config.json. Auto-generated if omitted.",
    )
    parser.add_argument(
        "--overrides",
        type=str,
        default=None,
        help="Optional path to overrides.json for manual obstacle/walkable adjustments.",
    )
    parser.add_argument(
        "--pois",
        type=str,
        default=None,
        help="Optional path to seed POIs JSON or CSV file.",
    )
    parser.add_argument(
        "--cell-size",
        type=float,
        default=0.15,
        help="Grid resolution cell size in meters (default: 0.15m)",
    )
    parser.add_argument(
        "--agent-radius",
        type=float,
        default=0.3,
        help="Agent clearance inflation radius in meters (default: 0.3m)",
    )
    return parser.parse_args()


def onboard_venue(
    model_path_str: str,
    venue_id: str,
    name: str = None,
    config_path_str: str = None,
    overrides_path_str: str = None,
    pois_path_str: str = None,
    cell_size: float = 0.15,
    agent_radius: float = 0.3,
):
    print("=" * 70)
    print(f"[*] INITIATING VENUE ONBOARDING PIPELINE: '{venue_id}'")
    print("=" * 70)

    model_src = Path(model_path_str).resolve()
    if not model_src.exists():
        raise FileNotFoundError(f"Model file does not exist: {model_src}")

    venue_dir = settings.VENUES_DIR / venue_id
    models_dir = venue_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    dest_model = models_dir / model_src.name
    if model_src.resolve() != dest_model.resolve():
        print(f"[1/7] Copying 3D asset -> {dest_model.relative_to(settings.BASE_DIR)}")
        shutil.copy2(model_src, dest_model)
    else:
        print(f"[1/7] 3D asset already at destination -> {dest_model.relative_to(settings.BASE_DIR)}")

    # Inspect 3D model geometry
    print(f"[2/7] Analyzing 3D mesh geometry...")
    mesh = trimesh.load(dest_model)
    bounds = mesh.bounds
    min_pt = Point3D(x=round(float(bounds[0][0]), 3), y=round(float(bounds[0][1]), 3), z=round(float(bounds[0][2]), 3))
    max_pt = Point3D(x=round(float(bounds[1][0]), 3), y=round(float(bounds[1][1]), 3), z=round(float(bounds[1][2]), 3))
    floor_height = round(min_pt.y, 2)
    bbox = BoundingBox.from_min_max(min_pt, max_pt)

    # Center spawn point
    spawn_x = round((min_pt.x + max_pt.x) / 2.0, 3)
    spawn_z = round((min_pt.z + max_pt.z) / 2.0 + 2.0, 3)
    spawn_y = round(floor_height + 1.6, 2)

    # Build or load configuration
    if config_path_str and Path(config_path_str).exists():
        print(f"[3/7] Loading provided config from {config_path_str}")
        with open(config_path_str, "r", encoding="utf-8") as f:
            venue_config = json.load(f)
    else:
        print(f"[3/7] Auto-synthesizing venue configuration...")
        venue_name = name or venue_id.replace("_", " ").replace("-", " ").title()
        venue_config = {
            "id": venue_id,
            "name": venue_name,
            "description": f"Digitized 3D twin of {venue_name} (IIT Bombay).",
            "model_file": f"models/{model_src.name}",
            "model_format": model_src.suffix.lstrip(".").lower(),
            "units": "meters",
            "up_axis": "Y",
            "floor_height": floor_height,
            "bounds": {
                "min": {"x": min_pt.x, "y": min_pt.y, "z": min_pt.z},
                "max": {"x": max_pt.x, "y": max_pt.y, "z": max_pt.z},
            },
            "spawn_point": {
                "position": {"x": spawn_x, "y": spawn_y, "z": spawn_z},
                "target": {"x": spawn_x, "y": floor_height + 1.0, "z": round(spawn_z - 3.0, 3)},
                "yaw": 0.0,
                "pitch": 0.0,
            },
            "custom": {
                "grid_resolution": cell_size,
                "agent_radius": agent_radius,
                "onboarded_at": "2026-09-24",
            },
        }

    # Save config.json
    dest_config = venue_dir / "config.json"
    with open(dest_config, "w", encoding="utf-8") as f:
        json.dump(venue_config, f, indent=2)

    # Copy manual overrides if provided
    if overrides_path_str and Path(overrides_path_str).exists():
        shutil.copy2(overrides_path_str, venue_dir / "overrides.json")
        print(f"[3b/7] Installed manual overrides file.")

    # Create temporary VenueMetadata object
    venue_meta = VenueMetadata(
        id=venue_id,
        name=venue_config.get("name", venue_id),
        description=venue_config.get("description"),
        model_format=venue_config.get("model_format", "glb"),
        units=venue_config.get("units", "meters"),
        up_axis=venue_config.get("up_axis", "Y"),
        floor_height=floor_height,
        bounds=bbox,
        spawn_point=SpawnPoint(
            position=Point3D(**venue_config["spawn_point"]["position"]),
            target=Point3D(**venue_config["spawn_point"]["target"]) if "target" in venue_config["spawn_point"] else None,
        ),
        model_filename=f"models/{model_src.name}",
        model_url=f"/static/venues/{venue_id}/models/{model_src.name}",
        config=venue_config,
    )

    # 4. Generate Occupancy Grid
    print(f"[4/7] Slicing mesh and rasterizing 2D occupancy grid...")
    grid = generate_occupancy_grid_from_mesh(
        venue=venue_meta,
        model_file_path=dest_model,
        cell_size=cell_size,
        agent_radius=agent_radius,
    )
    grid_file = venue_dir / "navmesh.npz"
    grid.save(grid_file)

    # 5. Connected Component & Disconnected Region Analysis
    print(f"[5/7] Analyzing walkable surface continuity & gaps...")
    report = analyze_walkable_regions(grid)

    # 6. Render Top-Down Debug Map
    debug_map_file = venue_dir / "debug_map.png"
    print(f"[6/7] Rendering visual debug navigation map -> {debug_map_file.name}")
    grid.render_debug_image(debug_map_file)

    # 7. Seed POIs if supplied
    pois_seeded = 0
    if pois_path_str and Path(pois_path_str).exists():
        print(f"[7/7] Ingesting initial POI dataset...")
        init_db()
        venue_service.load_all_venues()
        with open(pois_path_str, "r", encoding="utf-8") as f:
            poi_data = json.load(f)
        db = SessionLocal()
        try:
            pois_seeded, errors = poi_service.bulk_import(db, venue_id, poi_data)
            print(f"      Successfully seeded {pois_seeded} POIs.")
            if errors:
                for err in errors:
                    print(f"      [WARN] {err}")
        finally:
            db.close()
    else:
        print(f"[7/7] No POI file provided (skipping seed).")

    # Refresh server registry
    venue_service.load_all_venues()

    # PRINT COMPREHENSIVE VALIDATION REPORT
    print("\n" + "=" * 70)
    print(f"[REPORT] VENUE ONBOARDING VALIDATION REPORT: '{venue_id}'")
    print("=" * 70)
    print(f" - Venue Name:          {venue_meta.name}")
    print(f" - 3D Model Format:     {venue_meta.model_format.upper()} ({round(dest_model.stat().st_size / 1024, 1)} KB)")
    print(f" - Floor Height:        Y = {floor_height} m")
    print(f" - Bounding Box Min:    ({bbox.min.x}, {bbox.min.y}, {bbox.min.z})")
    print(f" - Bounding Box Max:    ({bbox.max.x}, {bbox.max.y}, {bbox.max.z})")
    print(f" - Space Dimensions:    {bbox.dimensions.x}m (W) x {bbox.dimensions.y}m (H) x {bbox.dimensions.z}m (D)")
    print(f" - Camera Spawn:        Eye=({spawn_x}, {spawn_y}, {spawn_z})")
    print(f" - Grid Dimensions:     {grid.cols} cols x {grid.rows} rows (cell: {grid.cell_size}m)")
    print(f" - Walkable Floor Area: {round(report.total_walkable_area_m2, 1)} m2 ({report.total_walkable_cells} cells)")
    print(f" - Walkable Continuity: {report.num_regions} distinct region(s) detected")

    if report.has_disconnected_regions:
        print(f"\n[WARNING] DISCONNECTED WALKABLE REGIONS DETECTED ({report.num_regions} islands):")
        for r in report.regions:
            primary_tag = "[PRIMARY COMPONENT]" if r["is_primary"] else "[ISOLATED ISLAND]"
            print(
                f"   Region #{r['region_id']}: {r['area_m2']} m2 ({r['percentage_of_walkable']}%) "
                f"{primary_tag} Bounds: X[{r['bounds']['min']['x']}, {r['bounds']['max']['x']}]"
            )
        print("   -> TIP: If islands are unintended scan gaps, add a bridging box to 'overrides.json'.")
    else:
        print("   [OK] Continuity check passed: 100% unified single connected walkable floor surface.")

    print(f" - POIs Registered:     {pois_seeded}")
    print(f" - Model Stream URL:    http://localhost:8000{venue_meta.model_url}")
    print(f" - Debug Visual Map:    http://localhost:8000/venues/{venue_id}/navmesh/debug.png")
    print("=" * 70)
    print("[SUCCESS] Onboarding Complete. Venue is immediately live and queryable by Three.js!\n")
    return venue_meta


if __name__ == "__main__":
    args = parse_args()
    onboard_venue(
        model_path_str=args.model,
        venue_id=args.venue_id,
        name=args.name,
        config_path_str=args.config,
        overrides_path_str=args.overrides,
        pois_path_str=args.pois,
        cell_size=args.cell_size,
        agent_radius=args.agent_radius,
    )
