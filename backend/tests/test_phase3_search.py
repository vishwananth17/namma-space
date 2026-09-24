import pytest
from app.db.session import SessionLocal, init_db
from app.models.poi import POIRecord
from app.services.poi_service import poi_service


@pytest.fixture(autouse=True)
def ensure_sample_pois():
    """Ensure sample lab has the standard POIs loaded before search tests."""
    init_db()
    db = SessionLocal()
    count = db.query(POIRecord).filter(POIRecord.venue_id == "sample_lab").count()
    if count < 8:
        # Load sample data
        from scripts.seed_pois import seed_venue_pois
        seed_venue_pois("sample_lab")
    db.close()


def test_search_exact_name_match(client):
    """Search for exact POI name should return top score and matched_field='name'."""
    response = client.get("/venues/sample_lab/search?q=Robotics Testing Arena")
    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] >= 1
    top_hit = data["results"][0]
    assert top_hit["id"] == "robotics-arena"
    assert top_hit["matched_field"] == "name"
    assert top_hit["score"] >= 95.0
    assert data["execution_time_ms"] < 50.0  # Performance target


def test_search_typo_tolerance(client):
    """Typo queries should successfully resolve to intended POIs."""
    # 1. 'wrkstation' -> workstation
    res1 = client.get("/venues/sample_lab/search?q=wrkstation")
    assert res1.status_code == 200
    hits1 = res1.json()["results"]
    assert len(hits1) >= 1
    assert "workstation" in hits1[0]["id"]

    # 2. 'bmbulab' -> Bambu Lab 3D Printing Hub
    res2 = client.get("/venues/sample_lab/search?q=bmbulab")
    assert res2.status_code == 200
    hits2 = res2.json()["results"]
    assert len(hits2) >= 1
    assert hits2[0]["id"] == "3d-printer-station"

    # 3. 'cofee' -> Coffee Corner
    res3 = client.get("/venues/sample_lab/search?q=cofee")
    assert res3.status_code == 200
    hits3 = res3.json()["results"]
    assert len(hits3) >= 1
    assert hits3[0]["id"] == "coffee-station"

    # 4. 'firt aid' -> First Aid Station
    res4 = client.get("/venues/sample_lab/search?q=firt aid")
    assert res4.status_code == 200
    hits4 = res4.json()["results"]
    assert len(hits4) >= 1
    assert hits4[0]["id"] == "first-aid-station"


def test_search_ranking_hierarchy(client):
    """Relevance ranking must prioritize: Name > Tags > Category > Description."""
    # Insert two test items
    db = SessionLocal()
    # Clean previous
    db.query(POIRecord).filter(POIRecord.id.in_(["test-rank-name", "test-rank-desc"])).delete()
    db.commit()

    # Item A has 'quantum' in NAME
    rec_a = POIRecord(
        id="test-rank-name",
        venue_id="sample_lab",
        name="Quantum Computing Bench",
        category="workstation",
        description="Standard lab desk.",
        pos_x=1.0,
        pos_y=0.5,
        pos_z=1.0,
        tags_json='["lab"]',
    )
    # Item B has 'quantum' only in DESCRIPTION
    rec_b = POIRecord(
        id="test-rank-desc",
        venue_id="sample_lab",
        name="Standard Wooden Desk",
        category="workstation",
        description="Equipped with a quantum simulator terminal.",
        pos_x=2.0,
        pos_y=0.5,
        pos_z=2.0,
        tags_json='["lab"]',
    )
    db.add_all([rec_a, rec_b])
    db.commit()
    db.close()

    response = client.get("/venues/sample_lab/search?q=quantum")
    assert response.status_code == 200
    results = response.json()["results"]
    ids = [r["id"] for r in results]

    assert "test-rank-name" in ids
    assert "test-rank-desc" in ids
    # Item with term in Name must rank before item with term in Description
    assert ids.index("test-rank-name") < ids.index("test-rank-desc")

    # Clean up
    db = SessionLocal()
    db.query(POIRecord).filter(POIRecord.id.in_(["test-rank-name", "test-rank-desc"])).delete()
    db.commit()
    db.close()


def test_search_with_category_filter(client):
    """Category filter must restrict results to the specified category only."""
    response = client.get("/venues/sample_lab/search?q=station&category=lab_equipment")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 1
    assert all(r["category"] == "lab_equipment" for r in results)
    # 3D printer is in lab_equipment, Workstation Alpha is not
    ids = [r["id"] for r in results]
    assert "3d-printer-station" in ids
    assert "workstation-alpha" not in ids


def test_search_with_user_position_and_distance(client):
    """When user position is supplied, each result must include accurate distance."""
    # Query position at workstation-alpha: (-5.0, 0.8, -3.0)
    response = client.get(
        "/venues/sample_lab/search?q=workstation&user_x=-5.0&user_y=0.8&user_z=-3.0"
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 2

    # First match should be workstation-alpha with distance approx 0
    alpha = next(r for r in results if r["id"] == "workstation-alpha")
    beta = next(r for r in results if r["id"] == "workstation-beta")

    assert alpha["distance"] == pytest.approx(0.0, abs=0.01)
    # Workstation beta is at (-5.0, 0.8, 3.0) -> distance exactly 6.0m
    assert beta["distance"] == pytest.approx(6.0, abs=0.01)


def test_search_distance_sorting(client):
    """When sort_by='distance' is requested, results must be ordered by distance ascending."""
    response = client.get(
        "/venues/sample_lab/search?q=workstation&user_x=-5.0&user_y=0.8&user_z=-3.0&sort_by=distance"
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 2

    distances = [r["distance"] for r in results if r["distance"] is not None]
    assert distances == sorted(distances)


def test_search_empty_queries(client):
    """Empty queries should return empty results or full category list if category provided."""
    # Empty query without category
    res1 = client.get("/venues/sample_lab/search?q=")
    assert res1.status_code == 200
    assert res1.json()["total_results"] == 0
    assert res1.json()["results"] == []

    # Whitespace query
    res2 = client.get("/venues/sample_lab/search?q=   ")
    assert res2.status_code == 200
    assert res2.json()["total_results"] == 0

    # Empty query with category filter
    res3 = client.get("/venues/sample_lab/search?q=&category=amenity")
    assert res3.status_code == 200
    assert res3.json()["total_results"] >= 2
    assert all(r["category"] == "amenity" for r in res3.json()["results"])


def test_search_special_characters_handling(client):
    """Special characters and punctuation must not crash the search service."""
    weird_queries = [
        "!@#$%^&*()",
        "<script>alert(1)</script>",
        "DROP TABLE pois;--",
        "???///+++===",
    ]
    for q in weird_queries:
        response = client.get(f"/venues/sample_lab/search?q={q}")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)


def test_search_nonexistent_venue(client):
    """Searching within an invalid venue ID must return 404."""
    response = client.get("/venues/nonexistent_venue_123/search?q=lab")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NOT_FOUND"


def test_search_performance_benchmark(client):
    """Verify search response time is well under the 50ms performance budget."""
    response = client.get("/venues/sample_lab/search?q=quadrotor drone arena")
    assert response.status_code == 200
    data = response.json()
    # Algorithm execution time
    assert data["execution_time_ms"] < 25.0
    # HTTP process time header
    header_ms = float(response.headers["x-process-time-ms"])
    assert header_ms < 50.0
