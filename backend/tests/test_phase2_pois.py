import pytest
from app.db.session import SessionLocal, init_db
from app.models.poi import POIRecord
from app.services.spatial_index import spatial_index_manager


@pytest.fixture(autouse=True)
def clean_test_pois():
    """Ensure database is initialized and clean test records before each test."""
    init_db()
    db = SessionLocal()
    # Remove any test-specific POIs
    db.query(POIRecord).filter(POIRecord.id.like("test-%")).delete()
    db.commit()
    db.close()
    spatial_index_manager.invalidate("sample_lab")
    yield


def test_create_poi_success(client):
    """POST /venues/{venue_id}/pois creates a POI with coordinates inside bounds."""
    payload = {
        "id": "test-poi-1",
        "name": "Test Microscope Bench",
        "category": "lab_equipment",
        "description": "High resolution optical microscope",
        "position": {"x": 2.5, "y": 1.0, "z": -1.5},
        "tags": ["microscope", "optics", "biology"],
        "floor": 0,
    }
    response = client.post("/venues/sample_lab/pois", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "test-poi-1"
    assert data["name"] == "Test Microscope Bench"
    assert data["category"] == "lab_equipment"
    assert data["position"]["x"] == 2.5
    assert "microscope" in data["tags"]
    assert "created_at" in data
    assert "updated_at" in data


def test_create_poi_out_of_bounds_rejected(client):
    """POST /venues/{venue_id}/pois with coordinates outside venue bounds returns 422."""
    payload = {
        "id": "test-poi-invalid-bounds",
        "name": "Out of bounds POI",
        "category": "amenity",
        "position": {"x": 50.0, "y": 1.0, "z": 100.0},  # sample_lab is [-10, 10] x [-7.5, 7.5]
    }
    response = client.post("/venues/sample_lab/pois", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "HTTP_ERROR" or data["error"] == "VALIDATION_ERROR"
    assert "outside the boundaries" in data["message"].lower() or "bounds" in data["message"].lower()


def test_create_poi_nonexistent_venue(client):
    """POST /venues/{venue_id}/pois with nonexistent venue returns 404."""
    payload = {
        "name": "Test Station",
        "category": "workstation",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    response = client.post("/venues/fake_venue_999/pois", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NOT_FOUND"


def test_get_poi_success(client):
    """GET /venues/{venue_id}/pois/{poi_id} returns the specific POI."""
    response = client.get("/venues/sample_lab/pois/workstation-alpha")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "workstation-alpha"
    assert "GPU Cluster" in data["name"]
    assert data["category"] == "workstation"


def test_get_poi_not_found(client):
    """GET /venues/{venue_id}/pois/{poi_id} for unknown POI returns 404."""
    response = client.get("/venues/sample_lab/pois/nonexistent-poi-xyz")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NOT_FOUND"


def test_list_pois_and_category_filtering(client):
    """GET /venues/{venue_id}/pois returns list and filters by category and tag."""
    # List all
    res_all = client.get("/venues/sample_lab/pois")
    assert res_all.status_code == 200
    all_pois = res_all.json()
    assert len(all_pois) >= 8

    # Filter by category = 'workstation'
    res_cat = client.get("/venues/sample_lab/pois?category=workstation")
    assert res_cat.status_code == 200
    cat_pois = res_cat.json()
    assert len(cat_pois) >= 2
    assert all(p["category"] == "workstation" for p in cat_pois)

    # Filter by tag = 'gpu'
    res_tag = client.get("/venues/sample_lab/pois?tag=gpu")
    assert res_tag.status_code == 200
    tag_pois = res_tag.json()
    assert len(tag_pois) >= 1
    assert any("gpu" in p["tags"] for p in tag_pois)


def test_update_poi(client):
    """PUT /venues/{venue_id}/pois/{poi_id} updates fields and validates bounds."""
    # Create test POI first
    client.post(
        "/venues/sample_lab/pois",
        json={
            "id": "test-update-me",
            "name": "Old Bench Name",
            "category": "workstation",
            "position": {"x": 1.0, "y": 0.5, "z": 1.0},
        },
    )

    # Update name and position
    update_res = client.put(
        "/venues/sample_lab/pois/test-update-me",
        json={
            "name": "Updated Bench Name",
            "position": {"x": 2.0, "y": 0.5, "z": 2.0},
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Updated Bench Name"
    assert updated_data["position"]["x"] == 2.0

    # Attempt updating with out-of-bounds coordinates
    oob_res = client.put(
        "/venues/sample_lab/pois/test-update-me",
        json={"position": {"x": 99.0, "y": 0.0, "z": 0.0}},
    )
    assert oob_res.status_code == 422


def test_delete_poi(client):
    """DELETE /venues/{venue_id}/pois/{poi_id} removes POI."""
    client.post(
        "/venues/sample_lab/pois",
        json={
            "id": "test-delete-me",
            "name": "Temporary POI",
            "category": "amenity",
            "position": {"x": 0.0, "y": 0.5, "z": 0.0},
        },
    )

    del_res = client.delete("/venues/sample_lab/pois/test-delete-me")
    assert del_res.status_code == 204

    # Subsequent GET must return 404
    get_res = client.get("/venues/sample_lab/pois/test-delete-me")
    assert get_res.status_code == 404


def test_spatial_radius_query_kdtree(client):
    """Spatial query with x, y, z, and radius uses KD-tree and returns sorted results with distance."""
    # Query within 5.0m from center (0, 0, 0)
    # robotics-arena is at (4.0, 0.6, 0.0) -> distance ~ 4.045m (inside)
    # conference-pod is at (6.5, 0.8, -5.0) -> distance ~ 8.24m (outside)
    response = client.get("/venues/sample_lab/pois?x=0.0&y=0.0&z=0.0&radius=5.0")
    assert response.status_code == 200
    results = response.json()

    assert len(results) > 0
    # Check that robotics-arena is found and within 5.0m
    arena_match = next((p for p in results if p["id"] == "robotics-arena"), None)
    assert arena_match is not None
    assert arena_match["distance"] <= 5.0

    # Check conference-pod is excluded
    pod_match = next((p for p in results if p["id"] == "conference-pod"), None)
    assert pod_match is None

    # Check results are sorted by distance ascending
    distances = [p["distance"] for p in results if p["distance"] is not None]
    assert distances == sorted(distances)


def test_spatial_nearest_k_query_kdtree(client):
    """Spatial query with nearest_k returns closest POIs to reference position."""
    # Query nearest 2 POIs to workstation-alpha at (-5.0, 0.8, -3.0)
    response = client.get("/venues/sample_lab/pois?x=-5.0&y=0.8&z=-3.0&nearest_k=2")
    assert response.status_code == 200
    results = response.json()

    assert len(results) == 2
    # The first result must be workstation-alpha itself with distance near 0.0
    assert results[0]["id"] == "workstation-alpha"
    assert results[0]["distance"] == pytest.approx(0.0, abs=0.01)
    assert results[1]["distance"] > results[0]["distance"]


def test_bulk_import_endpoint(client):
    """POST /venues/{venue_id}/pois/bulk imports multiple POIs in one request."""
    bulk_data = [
        {
            "id": "test-bulk-1",
            "name": "Bulk Desk A",
            "category": "workstation",
            "position": {"x": 1.0, "y": 0.5, "z": 1.0},
            "tags": ["bulk", "test"],
        },
        {
            "id": "test-bulk-2",
            "name": "Bulk Desk B",
            "category": "workstation",
            "position": {"x": 2.0, "y": 0.5, "z": 2.0},
            "tags": ["bulk", "test"],
        },
    ]
    response = client.post("/venues/sample_lab/pois/bulk", json=bulk_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 2
    assert data["errors_count"] == 0
