from app.models.common import BoundingBox, Point3D


def test_health_endpoint(client):
    """GET /health should return 200 with app info and venues count."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "app" in data
    assert data["registered_venues_count"] >= 1
    assert "sample_lab" in data["venue_ids"]


def test_list_venues(client):
    """GET /venues should return an array with venue summaries."""
    response = client.get("/venues")
    assert response.status_code == 200
    venues = response.json()
    assert isinstance(venues, list)
    assert len(venues) >= 1

    sample = next((v for v in venues if v["id"] == "sample_lab"), None)
    assert sample is not None
    assert sample["name"] == "Robotics & AI Research Lab"
    assert sample["model_format"] == "glb"
    assert sample["units"] == "meters"
    assert sample["up_axis"] == "Y"
    assert sample["floor_height"] == 0.0


def test_get_venue_detail_success(client):
    """GET /venues/{venue_id} should return full metadata, bounds, and spawn point."""
    response = client.get("/venues/sample_lab")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "sample_lab"
    assert "bounds" in data
    bounds = data["bounds"]
    assert bounds["min"]["x"] == -10.0
    assert bounds["max"]["x"] == 10.0
    assert bounds["dimensions"]["x"] == 20.0
    assert bounds["dimensions"]["z"] == 15.0

    assert "spawn_point" in data
    spawn = data["spawn_point"]
    assert spawn["position"]["x"] == 0.0
    assert spawn["position"]["y"] == 1.6
    assert spawn["position"]["z"] == 5.0

    assert "model_url" in data
    assert data["model_url"] == "/static/venues/sample_lab/models/sample_room.glb"


def test_get_venue_not_found(client):
    """GET /venues/nonexistent should return 404 with standardized error schema."""
    response = client.get("/venues/nonexistent_venue_xyz")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NOT_FOUND"
    assert "message" in data
    assert "nonexistent_venue_xyz" in data["message"]


def test_static_model_serving(client):
    """GET to model_url should return binary GLB content with proper MIME and caching headers."""
    response = client.get("/static/venues/sample_lab/models/sample_room.glb")
    assert response.status_code == 200
    # Content-Type should be model/gltf-binary or binary
    assert "model/gltf-binary" in response.headers.get("content-type", "") or "application/octet-stream" in response.headers.get("content-type", "")
    assert "cache-control" in response.headers
    # Check glTF binary header magic 'glTF' (0x46546C67)
    assert response.content[:4] == b"glTF"


def test_bounding_box_containment():
    """Verify 3D coordinate containment logic."""
    bbox = BoundingBox.from_min_max(
        Point3D(x=-10.0, y=0.0, z=-5.0),
        Point3D(x=10.0, y=3.0, z=5.0),
    )
    # Inside
    assert bbox.contains(Point3D(x=0.0, y=1.5, z=0.0)) is True
    # Exactly on boundary (within tolerance)
    assert bbox.contains(Point3D(x=10.0, y=0.0, z=5.0)) is True
    # Outside X
    assert bbox.contains(Point3D(x=15.0, y=1.5, z=0.0)) is False
    # Outside Y
    assert bbox.contains(Point3D(x=0.0, y=-2.0, z=0.0)) is False
    # Outside Z
    assert bbox.contains(Point3D(x=0.0, y=1.0, z=8.0)) is False


def test_process_time_and_cors_headers(client):
    """All responses should have X-Process-Time-Ms and CORS header when Origin is present."""
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "x-process-time-ms" in response.headers
    assert float(response.headers["x-process-time-ms"]) >= 0.0
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


def test_reload_venues_endpoint(client):
    """POST /venues/reload should reload and return list of venues."""
    response = client.post("/venues/reload")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_openapi_schema_generation(client):
    """GET /openapi.json should return a valid OpenAPI specification for Naresh and Swagger."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["openapi"].startswith("3.")
    assert "/health" in spec["paths"]
    assert "/venues" in spec["paths"]
    assert "/venues/{venue_id}" in spec["paths"]


def test_frontend_viewer_served(client):
    """GET / or GET /viewer should serve the 3D Digital Twin Viewer HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "NammaSpace 3D" in response.text
    assert "webgl-canvas" in response.text

