"""End-to-end interactive demonstration script for NammaSpace 3D digital twin backend.
Usable for judges, live presentation, and demo video recording.

Usage:
    python scripts/demo_pipeline.py
"""

import sys
import time
from pathlib import Path

# Ensure backend root is on Python path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def run_demo():
    client = TestClient(app)

    print_banner("1. BACKEND INITIALIZATION & HEALTH CHECK")
    res = client.get("/health")
    print(f"GET /health -> HTTP {res.status_code}")
    print(f"App: {res.json().get('app')} | Version: {res.json().get('version')}")
    print(f"Registered venues: {res.json().get('venue_ids')}")

    print_banner("2. VENUE METADATA & 3D ASSET STREAMING")
    res = client.get("/venues/sample_lab")
    data = res.json()
    print(f"Venue: '{data['name']}' (ID: {data['id']})")
    print(f"Bounds: Min({data['bounds']['min']['x']}, {data['bounds']['min']['z']}) -> Max({data['bounds']['max']['x']}, {data['bounds']['max']['z']})")
    print(f"Dimensions: {data['bounds']['dimensions']['x']}m (W) x {data['bounds']['dimensions']['z']}m (D)")
    print(f"Three.js Camera Spawn: Eye=({data['spawn_point']['position']['x']}, {data['spawn_point']['position']['y']}, {data['spawn_point']['position']['z']})")
    print(f"Model Serving Stream: http://localhost:8000{data['model_url']}")

    print_banner("3. SPATIAL DATA LAYER & KD-TREE QUERIES")
    # All POIs
    res = client.get("/venues/sample_lab/pois")
    pois = res.json()
    print(f"Total POIs in space: {len(pois)}")
    for p in pois[:4]:
        print(f" - [{p['category']}] {p['name']} at ({p['position']['x']}, {p['position']['y']}, {p['position']['z']})")

    # Radius query
    print("\n[KD-Tree Radius Query: Center (0, 0, 0), Radius = 5.0m]")
    res_rad = client.get("/venues/sample_lab/pois?x=0.0&y=0.0&z=0.0&radius=5.0")
    rad_pois = res_rad.json()
    for p in rad_pois:
        print(f" -> Found '{p['name']}' at distance {p['distance']}m")

    print_banner("4. TYPO-TOLERANT SEARCH ENGINE (RapidFuzz)")
    queries = ["wrkstation", "cofee", "bmbulab", "drone"]
    for q in queries:
        t0 = time.perf_counter()
        res_search = client.get(f"/venues/sample_lab/search?q={q}&user_x=-5.0&user_z=-3.0")
        t_ms = (time.perf_counter() - t0) * 1000.0
        results = res_search.json().get("results", [])
        if results:
            top = results[0]
            print(
                f" Query '{q}' -> Top Match: '{top['name']}' "
                f"(Score: {top['score']}% via {top['matched_field']}, Dist: {top.get('distance')}m) [{t_ms:.2f}ms]"
            )

    print_banner("5. OBSTACLE-AWARE PATHFINDING (8-Way A* + String-Pulling)")
    nav_req = {
        "start": "workstation-alpha",
        "goal": "coffee-station",
        "smooth_path": True,
    }
    print(f"Request: From '{nav_req['start']}' -> To '{nav_req['goal']}'")
    t0 = time.perf_counter()
    res_nav = client.post("/venues/sample_lab/navigate", json=nav_req)
    t_ms = (time.perf_counter() - t0) * 1000.0
    nav_data = res_nav.json()

    print(f"Route status: HTTP {res_nav.status_code}")
    print(f"Origin Snapped: {nav_data['origin_snapped']} | Destination Snapped: {nav_data['destination_snapped']}")
    print(f"Total Distance: {nav_data['total_distance_meters']} meters")
    print(f"Estimated Walking Time: {nav_data['estimated_walking_time_seconds']} seconds")
    print(f"Pathfinding Latency: {nav_data['execution_time_ms']} ms (Budget: < 200 ms)")
    print(f"Waypoints Count: {nav_data['total_waypoints']} (Smoothed: {nav_data['path_smoothed']})")
    print("3D World Waypoints Sequence:")
    for idx, wp in enumerate(nav_data["waypoints"]):
        print(f"   Step {idx + 1}: ({wp['x']}, {wp['y']}, {wp['z']})")

    # Turn-by-Turn Natural Directions
    print("\n[Natural Language Turn-by-Turn Directions]")
    for step in nav_data.get("directions", []):
        landmark_str = f" [Landmark: {step['nearby_landmark']}]" if step.get("nearby_landmark") else ""
        print(
            f"   #{step['step']} [{step['action']}] {step['instruction']} "
            f"({step['distance_meters']}m, {step['compass_bearing_deg']} deg {step['cardinal_direction']}){landmark_str}"
        )

    print_banner("5B. DYNAMIC OBSTACLE INJECTION & REAL-TIME REROUTING")
    # Inject a temporary hazard (e.g. wet floor spill) directly into the path
    mid_wp = nav_data["waypoints"][len(nav_data["waypoints"]) // 2]
    obs_req = {
        "id": "spill_hazard_01",
        "name": "Caution: Liquid Chemical Spill",
        "x": mid_wp["x"],
        "z": mid_wp["z"],
        "radius": 1.2,
    }
    print(f"Injecting dynamic obstacle: '{obs_req['name']}' at ({obs_req['x']}, {obs_req['z']}) [Radius = {obs_req['radius']}m]")
    res_obs = client.post("/venues/sample_lab/obstacles", json=obs_req)
    print(f"Obstacle registration status: HTTP {res_obs.status_code}")

    # Recalculate path - A* must divert around obstacle
    t0 = time.perf_counter()
    res_reroute = client.post("/venues/sample_lab/navigate", json=nav_req)
    t_ms = (time.perf_counter() - t0) * 1000.0
    reroute_data = res_reroute.json()

    print(f"Reroute status: HTTP {res_reroute.status_code} in {t_ms:.2f}ms")
    print(f"Rerouted due to obstacles: {reroute_data.get('rerouted_due_to_obstacles')}")
    print(f"Avoided Obstacles: {reroute_data.get('avoided_obstacles')}")
    print(f"New Total Distance: {reroute_data['total_distance_meters']}m (Baseline: {nav_data['total_distance_meters']}m)")
    print(f"New Waypoints Count: {reroute_data['total_waypoints']}")

    # Clean up obstacle
    client.delete("/venues/sample_lab/obstacles/spill_hazard_01")
    print("Cleaned up dynamic obstacle: Navigation restored to baseline.")

    print_banner("6. ROUND 3 VENUE ONBOARDING VERIFICATION")
    res_iitb = client.get("/venues/iitb_hall")
    if res_iitb.status_code == 200:
        iitb_data = res_iitb.json()
        print(f"Successfully loaded Round 3 Venue: '{iitb_data['name']}'")
        print(f"Model URL: {iitb_data['model_url']}")
        res_iitb_debug = client.get("/venues/iitb_hall/navmesh/debug")
        debug_info = res_iitb_debug.json()
        print(f"Navigation Grid: {debug_info['grid_width']}x{debug_info['grid_height']} cells ({debug_info['walkable_percentage']}% walkable)")
    else:
        print("Note: Run 'python scripts/onboard_venue.py' to register IIT Bombay venue.")

    print_banner("DEMO COMPLETED SUCCESSFULLY! ALL SYSTEMS GO FOR HACKATHON.")


if __name__ == "__main__":
    run_demo()
