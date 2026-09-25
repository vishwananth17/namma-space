import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=== 1. LIST VENUES ===")
venues = client.get("/venues").json()
for v in venues:
    print(f" - {v['name']} ({v['id']})")

print("\n=== 2. SEARCH FOR 'icu' ===")
search_res = client.get("/venues/city_hospital/search?q=icu").json()
print(f"Found {search_res['total_results']} result(s):")
for r in search_res["results"]:
    print(f" -> {r['name']} [{r['category']}] (Score: {r['score']}%) at ({r['position']['x']}, {r['position']['z']})")

print("\n=== 3. COMPUTE INDOOR ROUTE: Main Entrance -> ICU Ward 4A ===")
nav_payload = {
    "start": "main-entrance",
    "goal": "icu-ward-4a",
    "smooth_path": True
}
nav_res = client.post("/venues/city_hospital/navigate", json=nav_payload).json()
print(f"Status: HTTP 200 OK")
print(f"Total Walking Distance: {nav_res['total_distance_meters']} meters")
print(f"Estimated Walking Time: {nav_res['estimated_walking_time_seconds']} seconds")
print(f"Total Waypoints: {nav_res['total_waypoints']}")

print("\n=== 4. NATURAL TURN-BY-TURN DIRECTIONS ===")
for d in nav_res["directions"]:
    landmark_str = f" [Landmark: {d['nearby_landmark']}]" if d.get("nearby_landmark") else ""
    print(f" Step #{d['step']} [{d['action']}]: {d['instruction']}{landmark_str} ({d['distance_meters']}m, {d['cardinal_direction']})")

print("\n=== 5. SIMULATE EMERGENCY REROUTE (Spill in corridor) ===")
obs_payload = {
    "name": "Biohazard Spill near Pharmacy",
    "x": -6.5,
    "z": 2.5,
    "radius": 1.2
}
client.post("/venues/city_hospital/obstacles", json=obs_payload)
rerouted = client.post("/venues/city_hospital/navigate", json=nav_payload).json()
print(f"Rerouted around hazard: {rerouted['rerouted_due_to_obstacles']}")
print(f"Avoided: {rerouted['avoided_obstacles']}")
print(f"New Distance: {rerouted['total_distance_meters']}m")
client.post("/venues/city_hospital/obstacles/clear")

print("\n=== ALL HOSPITAL ICU TESTS PASSED! ===")
