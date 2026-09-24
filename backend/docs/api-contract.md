# NammaSpace 3D Digital Twin - API Contract

> **Target Audience:** Frontend Team (Naresh) & Integrators  
> **Backend Version:** v0.1.0  
> **Base URL:** `http://localhost:8000` (Local Dev)  
> **Interactive Swagger UI:** `http://localhost:8000/docs`  
> **OpenAPI JSON:** `http://localhost:8000/openapi.json`  

---

## 1. 3D Coordinate System & Spatial Conventions

To ensure seamless integration between the Python backend and Three.js viewer:

- **Coordinate System:** Right-Handed
- **Up-Axis:** `Y` is Up (ceiling), `X` is Right/Left (width), `Z` is Forward/Backward (depth).
- **Units:** Meters (`1.0` unit = `1.0` meter).
- **Floor Level:** Default floor reference is at `y = 0.0` meters unless specified otherwise in venue metadata.
- **Camera Spawn Point:**
  - `position`: `[x, y, z]` camera eye position (typically eye height `y = 1.6m`).
  - `target`: `[x, y, z]` point in 3D space the camera looks towards initially.

---

## 2. Global Response Headers

All HTTP responses include:
- `X-Process-Time-Ms`: Execution latency in milliseconds (e.g. `2.45`).
- `Access-Control-Allow-Origin: *` (CORS enabled for dev servers at `http://localhost:3000`, `5173`, etc.).

---

## 3. Standard Error Envelope

When any request fails (4xx or 5xx), the response body is guaranteed to match:

```json
{
  "error": "NOT_FOUND",
  "message": "Venue 'unknown_id' does not exist.",
  "details": null
}
```

Validation errors (HTTP 422) include detailed field breakdown in `"details"`.

---

## 4. Endpoints

### 4.1 System Health
- **Route:** `GET /health`
- **Description:** Checks backend operational status and registered venues.

#### Response `200 OK`
```json
{
  "status": "healthy",
  "app": "NammaSpace 3D Digital Twin Backend",
  "version": "0.1.0",
  "environment": "development",
  "registered_venues_count": 1,
  "venue_ids": ["sample_lab"]
}
```

---

### 4.2 List All Venues
- **Route:** `GET /venues`
- **Description:** Returns a summary array of all available 3D venues.

#### Response `200 OK`
```json
[
  {
    "id": "sample_lab",
    "name": "Robotics & AI Research Lab",
    "description": "Synthetic benchmark venue: 20m x 15m indoor lab environment with workstations, robotics pen, and conference area.",
    "model_format": "glb",
    "units": "meters",
    "up_axis": "Y",
    "floor_height": 0.0
  }
]
```

---

### 4.3 Get Venue Metadata & Model URL
- **Route:** `GET /venues/{venue_id}`
- **Description:** Returns the 3D bounding box, camera spawn point, and direct model download/stream URL for the specified venue.

#### Example Request
```http
GET /venues/sample_lab HTTP/1.1
Host: localhost:8000
```

#### Response `200 OK`
```json
{
  "id": "sample_lab",
  "name": "Robotics & AI Research Lab",
  "description": "Synthetic benchmark venue: 20m x 15m indoor lab environment with workstations, robotics pen, and conference area.",
  "model_format": "glb",
  "units": "meters",
  "up_axis": "Y",
  "floor_height": 0.0,
  "bounds": {
    "min": { "x": -10.0, "y": 0.0, "z": -7.5 },
    "max": { "x": 10.0, "y": 3.0, "z": 7.5 },
    "dimensions": { "x": 20.0, "y": 3.0, "z": 15.0 }
  },
  "spawn_point": {
    "position": { "x": 0.0, "y": 1.6, "z": 5.0 },
    "target": { "x": 0.0, "y": 1.2, "z": 0.0 },
    "yaw": 0.0,
    "pitch": -0.05
  },
  "model_filename": "models/sample_room.glb",
  "model_url": "/static/venues/sample_lab/models/sample_room.glb",
  "config": {
    "building": "Department of Computer Science & Engineering",
    "campus": "IIT Bombay"
  }
}
```

#### Response `404 Not Found`
```json
{
  "error": "NOT_FOUND",
  "message": "Venue 'iitb_old_hall' does not exist.",
  "details": null
}
```

---

### 4.4 Static 3D Model Serving
- **Route:** `GET /static/venues/{venue_id}/{model_path}`
- **Example:** `GET http://localhost:8000/static/venues/sample_lab/models/sample_room.glb`
- **MIME Types Served:**
  - `.glb` &rarr; `model/gltf-binary`
  - `.gltf` &rarr; `model/gltf+json`
  - `.ply` &rarr; `application/octet-stream`
  - `.obj` &rarr; `text/plain`
- **Caching:** `Cache-Control: public, max-age=86400, stale-while-revalidate=3600`

---

### 4.5 List & Spatially Query POIs
- **Route:** `GET /venues/{venue_id}/pois`
- **Query Parameters:**
  - `category` (optional, string): filter by category (e.g. `workstation`, `lab_equipment`, `exit`, `amenity`, `safety`)
  - `tag` (optional, string): filter by exact tag (e.g. `gpu`, `coffee`)
  - `floor` (optional, integer): filter by floor index (e.g. `0`)
  - **Spatial Radius Search:**
    - `x`, `y`, `z` (floats): query center point in meters
    - `radius` (float, meters): returns all POIs within radius sphere, sorted ascending by distance
  - **Spatial Nearest Search:**
    - `x`, `y`, `z` (floats): reference point in meters
    - `nearest_k` (integer, default 1, max 50): returns `k` closest POIs with distance

#### Example: Spatial Radius Query
```http
GET /venues/sample_lab/pois?x=0.0&y=0.0&z=0.0&radius=5.0 HTTP/1.1
```
#### Response `200 OK`
```json
[
  {
    "id": "robotics-arena",
    "venue_id": "sample_lab",
    "name": "Robotics Testing Arena",
    "category": "lab_equipment",
    "description": "Enclosed 4m x 4m netted zone for autonomous quadrotor flight and ground rover navigation trials.",
    "position": { "x": 4.0, "y": 0.6, "z": 0.0 },
    "tags": ["robotics", "drone", "rover", "arena", "safety_cage"],
    "floor": 0,
    "distance": 4.045,
    "created_at": "2026-09-24T23:10:40Z",
    "updated_at": "2026-09-24T23:10:40Z"
  }
]
```

---

### 4.6 Create a POI
- **Route:** `POST /venues/{venue_id}/pois`
- **Status:** `201 Created`
- **Behavior:** Validates that `position` falls inside the venue's 3D bounding box. Returns `422 Unprocessable Entity` if outside bounds.

#### Request Body
```json
{
  "id": "gpu-rig-1",
  "name": "Workstation Alpha (GPU Cluster)",
  "category": "workstation",
  "description": "Dual RTX 4090 node",
  "position": { "x": -5.0, "y": 0.8, "z": -3.0 },
  "tags": ["gpu", "cuda"],
  "floor": 0
}
```

---

### 4.7 Get Single POI
- **Route:** `GET /venues/{venue_id}/pois/{poi_id}`
- **Response:** `POIResponse` or `404 Not Found`

---

### 4.8 Update a POI
- **Route:** `PUT /venues/{venue_id}/pois/{poi_id}`
- **Behavior:** Accepts partial updates. If `position` is provided, coordinates are validated against venue bounds.

---

### 4.9 Delete a POI
- **Route:** `DELETE /venues/{venue_id}/pois/{poi_id}`
- **Status:** `204 No Content`

---

### 4.10 Bulk Import POIs
- **Route:** `POST /venues/{venue_id}/pois/bulk`
- **Request:** Array of POI objects
- **Response:** `{ "status": "success", "imported_count": 8, "errors_count": 0, "errors": [] }`

---

### 4.11 Search POIs & Objects (Typo-Tolerant)
- **Route:** `GET /venues/{venue_id}/search`
- **Description:** Fuzzy, typo-tolerant search across POI names, tags, categories, and descriptions. Uses weighted scoring: `name (1.0) > tags (0.85) > category (0.70) > description (0.50)`.
- **Query Parameters:**
  - `q` (string, default `""`): Search keywords or phrases (e.g. `wrkstation`, `drone`, `bmbulab`, `coffee`)
  - `category` (optional, string): Filter by category
  - `limit` (integer, default `10`, max `100`): Max results to return
  - `user_x`, `user_y`, `user_z` (optional, floats): User's current avatar/camera position in meters
  - `sort_by` (optional, string, default `"relevance"`): `"relevance"` (highest score first) or `"distance"` (closest to user first)

#### Example Request
```http
GET /venues/sample_lab/search?q=wrkstation&user_x=-5.0&user_y=0.8&user_z=-3.0 HTTP/1.1
```

#### Response `200 OK`
```json
{
  "query": "wrkstation",
  "venue_id": "sample_lab",
  "category_filter": null,
  "total_results": 2,
  "execution_time_ms": 1.25,
  "results": [
    {
      "id": "workstation-alpha",
      "venue_id": "sample_lab",
      "name": "Workstation Alpha (GPU Cluster)",
      "category": "workstation",
      "description": "High-performance compute rig equipped with dual RTX 4090 GPUs for deep learning models.",
      "position": { "x": -5.0, "y": 0.8, "z": -3.0 },
      "tags": ["workstation", "gpu", "desktop", "cuda", "compute"],
      "floor": 0,
      "score": 85.0,
      "matched_field": "name",
      "distance": 0.0
    },
    {
      "id": "workstation-beta",
      "venue_id": "sample_lab",
      "name": "Workstation Beta (Data Science)",
      "category": "workstation",
      "description": "Ergonomic desk with dual 4K monitors and high-speed fiber uplink.",
      "position": { "x": -5.0, "y": 0.8, "z": 3.0 },
      "tags": ["workstation", "python", "monitor", "workbench"],
      "floor": 0,
      "score": 85.0,
      "matched_field": "name",
      "distance": 6.0
    }
  ]
}
```

### 4.12 Compute Obstacle-Aware Navigation Route
- **Route:** `POST /venues/{venue_id}/navigate`
- **Description:** Calculates an obstacle-avoiding 3D walking route using 8-way A* pathfinding and line-of-sight path smoothing.
- **Request Body Options:**
  - Can specify origin and destination as POI IDs:
    ```json
    {
      "start": "workstation-alpha",
      "goal": "coffee-station",
      "smooth_path": true
    }
    ```
  - Or as direct 3D world coordinates `{x, y, z}`:
    ```json
    {
      "start": { "x": -5.0, "y": 0.8, "z": -3.0 },
      "goal": { "x": 8.5, "y": 0.9, "z": 5.5 },
      "smooth_path": true
    }
    ```
  - Or mix and match (`start: "workstation-alpha"`, `goal: { "x": 0.0, "y": 0.0, "z": 4.0 }`).

#### Response `200 OK`
```json
{
  "venue_id": "sample_lab",
  "origin_name": "Workstation Alpha (GPU Cluster)",
  "destination_name": "Refreshment & Coffee Corner",
  "origin_snapped": false,
  "destination_snapped": false,
  "waypoints": [
    { "x": -5.0, "y": 0.1, "z": -3.0 },
    { "x": -2.8, "y": 0.1, "z": -1.2 },
    { "x": 1.5, "y": 0.1, "z": 2.1 },
    { "x": 8.5, "y": 0.1, "z": 5.5 }
  ],
  "total_waypoints": 4,
  "total_distance_meters": 16.42,
  "estimated_walking_time_seconds": 13.7,
  "execution_time_ms": 14.8,
  "path_smoothed": true
}
```

#### Error Responses
- `400 Bad Request`: `{"error": "NO_PATH_FOUND", "message": "No path exists between start and goal. Obstacles completely block traversal.", "details": null}`
- `422 Unprocessable Entity`: `{"error": "START_OR_GOAL_BLOCKED", "message": "Position is trapped inside an obstacle and cannot be snapped.", "details": null}`
- `404 Not Found`: If venue or POI ID is not registered.

---

### 4.13 Navigation Grid Debug Map
- **Route:** `GET /venues/{venue_id}/navmesh/debug`
- **Output:** Returns JSON metadata of the grid (dimensions, cell size, walkable cell counts, percentage).
- **Image Direct Route:** `GET /venues/{venue_id}/navmesh/debug.png` (or add `?format=image`)
  - Streams high-contrast PNG top-down map showing walls (black), inflated clearance buffer (salmon), and walkable floor (white).

---

## 5. Three.js Frontend Integration Snippet (for Naresh)

```javascript
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

const BACKEND_BASE = 'http://localhost:8000';

async function initVenue(venueId) {
  // 1. Fetch metadata from backend
  const res = await fetch(`${BACKEND_BASE}/venues/${venueId}`);
  if (!res.ok) throw new Error(`Venue ${venueId} not found`);
  const meta = await res.json();

  // 2. Position Three.js camera from backend spawn point
  camera.position.set(
    meta.spawn_point.position.x,
    meta.spawn_point.position.y,
    meta.spawn_point.position.z
  );
  if (meta.spawn_point.target) {
    controls.target.set(
      meta.spawn_point.target.x,
      meta.spawn_point.target.y,
      meta.spawn_point.target.z
    );
  }
  controls.update();

  // 3. Load 3D model with GLTFLoader
  const loader = new GLTFLoader();
  const fullModelUrl = `${BACKEND_BASE}${meta.model_url}`;
  
  loader.load(
    fullModelUrl,
    (gltf) => {
      scene.add(gltf.scene);
      console.log(`Loaded venue '${meta.name}' successfully!`);
    }
  );

  // 4. Fetch and render 3D POI pins
  const poisRes = await fetch(`${BACKEND_BASE}/venues/${venueId}/pois`);
  const pois = await poisRes.json();
  
  const pinGeometry = new THREE.SphereGeometry(0.18, 16, 16);
  const pinMaterial = new THREE.MeshStandardMaterial({ color: 0x3b82f6, roughness: 0.3 });

  pois.forEach(poi => {
    const pin = new THREE.Mesh(pinGeometry, pinMaterial);
    pin.position.set(poi.position.x, poi.position.y + 0.3, poi.position.z);
    pin.userData = poi; // Attach POI metadata for raycasting / click popup
    scene.add(pin);
  });
}

// 5. Search bar autocomplete and camera fly-to
async function searchAndFocus(venueId, searchTerm) {
  const url = `${BACKEND_BASE}/venues/${venueId}/search?q=${encodeURIComponent(searchTerm)}&user_x=${camera.position.x}&user_z=${camera.position.z}`;
  const res = await fetch(url);
  const data = await res.json();
  
  if (data.results.length > 0) {
    const targetPoi = data.results[0];
    console.log(`Focusing on match: ${targetPoi.name} (${targetPoi.score}% match via ${targetPoi.matched_field})`);
    
    // Smoothly fly camera to POI
    controls.target.set(targetPoi.position.x, targetPoi.position.y, targetPoi.position.z);
    camera.position.set(targetPoi.position.x, targetPoi.position.y + 2.0, targetPoi.position.z + 3.0);
    controls.update();
  }
}

// 6. Draw obstacle-avoiding navigation path line in 3D
let currentPathLine = null;

async function navigateBetween(venueId, startPoiId, goalPoiId) {
  const res = await fetch(`${BACKEND_BASE}/venues/${venueId}/navigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      start: startPoiId,
      goal: goalPoiId,
      smooth_path: true
    })
  });
  const data = await res.json();
  console.log(`Route found: ${data.total_distance_meters}m, estimated time: ${data.estimated_walking_time_seconds}s`);

  // Remove previous route line if present
  if (currentPathLine) scene.remove(currentPathLine);

  // Build Three.js 3D path line
  const points = data.waypoints.map(wp => new THREE.Vector3(wp.x, wp.y + 0.15, wp.z));
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({ color: 0x00e676, linewidth: 4 });
  currentPathLine = new THREE.Line(geometry, material);
  scene.add(currentPathLine);
}
```
