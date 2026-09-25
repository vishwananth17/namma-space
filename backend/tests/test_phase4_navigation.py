import pytest
from app.algorithms.astar import (
    AStarPathfinder,
    NoPathFoundError,
    NoWalkableCellError,
)
from app.algorithms.occupancy_grid import (
    OccupancyGrid,
    STATE_OBSTACLE,
    STATE_WALKABLE,
)
from app.algorithms.path_smoothing import smooth_path
from app.db.session import SessionLocal, init_db
from app.models.common import BoundingBox, Point3D
from app.models.poi import POIRecord


@pytest.fixture(autouse=True)
def setup_venue_and_pois():
    """Ensure database and POIs are seeded before navigation tests."""
    init_db()
    db = SessionLocal()
    count = db.query(POIRecord).filter(POIRecord.venue_id == "sample_lab").count()
    if count < 8:
        from scripts.seed_pois import seed_venue_pois
        seed_venue_pois("sample_lab")
    db.close()


def test_navigation_open_room_straight_path(client):
    """Pathfinding in open walkable corridor produces direct route."""
    payload = {
        "start": {"x": 0.0, "y": 0.0, "z": 2.0},
        "goal": {"x": 0.0, "y": 0.0, "z": 5.0},
        "smooth_path": True,
    }
    response = client.post("/venues/sample_lab/navigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["venue_id"] == "sample_lab"
    assert data["total_distance_meters"] == pytest.approx(3.0, abs=0.2)
    assert len(data["waypoints"]) >= 2
    assert data["execution_time_ms"] < 200.0  # Performance target


def test_navigation_around_obstacles(client):
    """Path must successfully circumvent obstacles between West and East wings."""
    # From Workstation Alpha (-5.0, 0.8, -3.0) to Coffee Station (8.5, 0.9, 5.5)
    payload = {
        "from_position": {"x": -5.0, "y": 0.0, "z": -3.0},
        "to_position": {"x": 8.0, "y": 0.0, "z": 5.0},
        "smooth_path": True,
    }
    response = client.post("/venues/sample_lab/navigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_distance_meters"] > 14.0
    assert len(data["waypoints"]) >= 3
    assert data["execution_time_ms"] < 200.0


def test_navigation_between_poi_ids(client):
    """Direct POI-to-POI navigation by slug."""
    payload = {
        "start": "workstation-alpha",
        "goal": "conference-pod",
        "smooth_path": True,
    }
    response = client.post("/venues/sample_lab/navigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "GPU Cluster" in data["origin_name"]
    assert "Conference Pod" in data["destination_name"]
    assert data["total_distance_meters"] > 0
    assert len(data["waypoints"]) >= 2


def test_navigation_start_goal_snapping(client):
    """Coordinates inside an obstacle are automatically snapped to nearest walkable cell."""
    # Workstation desk at (-5.0, -3.0) is an obstacle; snap should engage
    payload = {
        "start": {"x": -5.0, "y": 0.0, "z": -3.0},
        "goal": {"x": 0.0, "y": 0.0, "z": 4.0},
        "smooth_path": True,
    }
    response = client.post("/venues/sample_lab/navigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["origin_snapped"] is True


def test_astar_corner_cutting_prevention():
    """Diagonal movement through an obstacle corner is strictly forbidden."""
    # 5x5 synthetic grid
    min_pt = Point3D(x=0.0, y=0.0, z=0.0)
    max_pt = Point3D(x=5.0, y=3.0, z=5.0)
    grid = OccupancyGrid(bounds=BoundingBox.from_min_max(min_pt, max_pt), cell_size=1.0)
    # Mark all walkable
    grid.data[:, :] = STATE_WALKABLE

    # Place an L-shaped corner wall:
    # Cell (1, 2) is obstacle, and (2, 1) is obstacle
    grid.data[2, 1] = STATE_OBSTACLE
    grid.data[1, 2] = STATE_OBSTACLE

    # Moving diagonally from (1, 1) to (2, 2) cuts through the obstacle corner
    pathfinder = AStarPathfinder(grid)
    # Start at cell (1, 1) -> world (1.5, 1.5)
    # Goal at cell (2, 2) -> world (2.5, 2.5)
    path, _, _ = pathfinder.find_path((1.5, 1.5), (2.5, 2.5))

    # Path cannot take direct 1-step diagonal [(1, 1), (2, 2)]
    # It must take a longer detour or avoid the diagonal
    assert path != [(1, 1), (2, 2)]


def test_astar_no_path_found_exception():
    """When a room is completely enclosed by walls, NoPathFoundError is raised."""
    min_pt = Point3D(x=0.0, y=0.0, z=0.0)
    max_pt = Point3D(x=10.0, y=3.0, z=10.0)
    grid = OccupancyGrid(bounds=BoundingBox.from_min_max(min_pt, max_pt), cell_size=1.0)
    grid.data[:, :] = STATE_WALKABLE

    # Build solid vertical wall splitting grid at col=5
    grid.data[:, 5] = STATE_OBSTACLE

    pathfinder = AStarPathfinder(grid)
    with pytest.raises(NoPathFoundError):
        pathfinder.find_path(start_world=(2.5, 2.5), goal_world=(8.5, 8.5), snap=False)


def test_path_smoothing_string_pulling():
    """String-pulling reduces zig-zag waypoints down to straight segments."""
    min_pt = Point3D(x=0.0, y=0.0, z=0.0)
    max_pt = Point3D(x=20.0, y=3.0, z=20.0)
    grid = OccupancyGrid(bounds=BoundingBox.from_min_max(min_pt, max_pt), cell_size=1.0)
    grid.data[:, :] = STATE_WALKABLE

    # Create artificial jagged grid path of 10 steps along diagonal
    jagged_path = [(i, i) for i in range(10)]
    smoothed = smooth_path(grid, jagged_path)

    # In open space, smooth_path should reduce 10 steps to just 2 points: start and goal
    assert len(smoothed) == 2
    assert smoothed[0] == (0, 0)
    assert smoothed[-1] == (9, 9)


def test_navmesh_debug_json_endpoint(client):
    """GET /venues/{venue_id}/navmesh/debug returns grid metadata."""
    response = client.get("/venues/sample_lab/navmesh/debug")
    assert response.status_code == 200
    data = response.json()
    assert data["venue_id"] == "sample_lab"
    assert data["grid_width"] > 0
    assert data["grid_height"] > 0
    assert data["walkable_percentage"] > 50.0
    assert data["debug_map_url"].endswith(".png")


def test_navmesh_debug_png_endpoint(client):
    """GET /venues/{venue_id}/navmesh/debug.png streams valid PNG image bytes."""
    response = client.get("/venues/sample_lab/navmesh/debug.png")
    assert response.status_code == 200
    assert "image/png" in response.headers["content-type"]
    # PNG signature: 0x89 50 4E 47 0D 0A 1A 0A
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_navigation_performance_benchmark(client):
    """Pathfinding across the 20m venue must execute well under 200ms."""
    payload = {
        "start": {"x": -8.0, "y": 0.0, "z": -6.0},
        "goal": {"x": 8.0, "y": 0.0, "z": 6.0},
        "smooth_path": True,
    }
    response = client.post("/venues/sample_lab/navigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Algorithm execution time
    assert data["execution_time_ms"] < 100.0
    # HTTP roundtrip time
    header_ms = float(response.headers["x-process-time-ms"])
    assert header_ms < 200.0


def test_navigation_turn_by_turn_directions(client):
    """Pathfinding response must synthesize human-readable turn-by-turn directions."""
    payload = {
        "start": "workstation-alpha",
        "goal": "coffee-station",
        "smooth_path": True,
    }
    response = client.post("/venues/sample_lab/navigate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "directions" in data
    directions = data["directions"]
    assert len(directions) >= 2

    # First step is departure
    step1 = directions[0]
    assert step1["step"] == 1
    assert step1["action"] == "START"
    assert "Depart from" in step1["instruction"]
    assert step1["distance_meters"] > 0.0
    assert 0 <= step1["compass_bearing_deg"] <= 359
    assert step1["cardinal_direction"] in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    # Final step is arrival
    step_last = directions[-1]
    assert step_last["action"] == "ARRIVE"
    assert "Arrive at" in step_last["instruction"]


def test_dynamic_obstacles_crud_and_rerouting(client):
    """Dynamic obstacles are registered, avoid collision via A* rerouting, and can be cleared."""
    # 1. Clear any prior obstacles
    res_clear = client.post("/venues/sample_lab/obstacles/clear")
    assert res_clear.status_code == 200

    # 2. Get baseline path without obstacles
    nav_payload = {
        "start": "workstation-alpha",
        "goal": "coffee-station",
        "smooth_path": True,
    }
    res_base = client.post("/venues/sample_lab/navigate", json=nav_payload)
    assert res_base.status_code == 200
    base_data = res_base.json()
    base_dist = base_data["total_distance_meters"]

    # Pick a point along the initial path to block
    midpoint = base_data["waypoints"][len(base_data["waypoints"]) // 2]

    # 3. Register a dynamic obstacle at midpoint
    obs_payload = {
        "id": "test_spill_hazard",
        "name": "Hazardous Chemical Spill",
        "x": midpoint["x"],
        "z": midpoint["z"],
        "radius": 1.0,
    }
    res_create = client.post("/venues/sample_lab/obstacles", json=obs_payload)
    assert res_create.status_code == 201
    created_obs = res_create.json()
    assert created_obs["id"] == "test_spill_hazard"
    assert created_obs["name"] == "Hazardous Chemical Spill"

    # 4. List obstacles
    res_list = client.get("/venues/sample_lab/obstacles")
    assert res_list.status_code == 200
    obs_list = res_list.json()
    assert any(o["id"] == "test_spill_hazard" for o in obs_list)

    # 5. Navigate again - path must successfully route around obstacle
    res_rerouted = client.post("/venues/sample_lab/navigate", json=nav_payload)
    assert res_rerouted.status_code == 200
    rerouted_data = res_rerouted.json()
    assert rerouted_data["rerouted_due_to_obstacles"] is True
    assert "Hazardous Chemical Spill" in rerouted_data["avoided_obstacles"]

    # 6. Delete obstacle and verify it is gone
    res_del = client.delete("/venues/sample_lab/obstacles/test_spill_hazard")
    assert res_del.status_code == 200
    res_list_after = client.get("/venues/sample_lab/obstacles")
    assert not any(o["id"] == "test_spill_hazard" for o in res_list_after.json())

