import shutil
from pathlib import Path
import pytest

from app.algorithms.occupancy_grid import (
    OccupancyGrid,
    STATE_OBSTACLE,
    STATE_WALKABLE,
)
from app.algorithms.region_analyzer import analyze_walkable_regions
from app.config import settings
from app.models.common import BoundingBox, Point3D
from scripts.onboard_venue import onboard_venue


@pytest.fixture
def temp_venue_cleanup():
    """Ensure temporary test venues are cleaned up after test run."""
    venue_id = "test_iitb_audit"
    yield venue_id
    venue_dir = settings.VENUES_DIR / venue_id
    if venue_dir.exists():
        shutil.rmtree(venue_dir, ignore_errors=True)


def test_onboard_new_venue_pipeline(temp_venue_cleanup, client):
    """Single-command onboarding registers a venue, generates navmesh, and serves it live."""
    model_src = settings.VENUES_DIR / "sample_lab" / "models" / "sample_room.glb"
    venue_id = temp_venue_cleanup

    # Run onboarding pipeline
    venue_meta = onboard_venue(
        model_path_str=str(model_src),
        venue_id=venue_id,
        name="IIT Bombay Auditorium",
        cell_size=0.20,
        agent_radius=0.3,
    )

    assert venue_meta.id == venue_id
    assert venue_meta.name == "IIT Bombay Auditorium"

    # Verify files created on disk
    venue_dir = settings.VENUES_DIR / venue_id
    assert (venue_dir / "config.json").exists()
    assert (venue_dir / "navmesh.npz").exists()
    assert (venue_dir / "debug_map.png").exists()
    assert (venue_dir / "models" / "sample_room.glb").exists()

    # Verify venue is immediately queryable via REST API
    res = client.get(f"/venues/{venue_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "IIT Bombay Auditorium"
    assert data["bounds"]["dimensions"]["x"] > 0

    # Verify navigation works on newly onboarded venue
    nav_res = client.post(
        f"/venues/{venue_id}/navigate",
        json={
            "start": {"x": 0.0, "y": 0.0, "z": 0.0},
            "goal": {"x": 2.0, "y": 0.0, "z": 2.0},
            "smooth_path": True,
        },
    )
    assert nav_res.status_code == 200
    assert nav_res.json()["total_distance_meters"] > 0


def test_disconnected_region_analysis():
    """Connected component labeling must accurately detect disconnected scan gaps and islands."""
    min_pt = Point3D(x=0.0, y=0.0, z=0.0)
    max_pt = Point3D(x=20.0, y=3.0, z=10.0)
    grid = OccupancyGrid(bounds=BoundingBox.from_min_max(min_pt, max_pt), cell_size=1.0)
    # Mark all as walkable
    grid.data[:, :] = STATE_WALKABLE

    # Divide grid into 2 separate rooms by building a solid wall at column 10
    grid.data[:, 10] = STATE_OBSTACLE

    report = analyze_walkable_regions(grid)
    assert report.has_disconnected_regions is True
    assert report.num_regions == 2
    assert report.regions[0]["is_primary"] is True
    assert report.regions[1]["is_primary"] is False
    # Sum of percentage is ~100%
    total_pct = sum(r["percentage_of_walkable"] for r in report.regions)
    assert total_pct == pytest.approx(100.0, abs=0.5)


def test_manual_overrides_application(client):
    """Manual overrides in overrides.json or config must correctly add/remove obstacles and walkable cells."""
    min_pt = Point3D(x=0.0, y=0.0, z=0.0)
    max_pt = Point3D(x=10.0, y=3.0, z=10.0)
    grid = OccupancyGrid(bounds=BoundingBox.from_min_max(min_pt, max_pt), cell_size=1.0)
    grid.data[:, :] = STATE_WALKABLE

    # Apply manual obstacle override
    grid.set_obstacle_box(min_x=2.0, max_x=4.0, min_z=2.0, max_z=4.0)
    # Cells in [2, 4] x [2, 4] must be STATE_OBSTACLE
    c, r = grid.world_to_grid(3.0, 3.0)
    assert grid.data[r, c] == STATE_OBSTACLE

    # Apply manual walkable override (clearing part of the obstacle)
    c_clear, r_clear = grid.world_to_grid(3.0, 3.0)
    grid.data[r_clear, c_clear] = STATE_WALKABLE
    assert grid.is_walkable(c_clear, r_clear) is True
