# 🌐 NammaSpace 3D — Indoor Digital Twin & Spatial Navigation Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Three.js](https://img.shields.io/badge/Three.js-r160-black.svg?logo=three.js&logoColor=white)](https://threejs.org)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-44%20Passed%20(100%25)-10b981.svg)]()
[![License](https://img.shields.io/badge/License-MIT-blue.svg)]()

> **Production-grade spatial computing, 3D digital twin visualization, typo-tolerant POI search, and obstacle-aware indoor pathfinding engine.**  
> Built for web browsers, desktop displays, and edge devices with sub-millisecond spatial queries and sub-25ms path planning.

---

## 🌟 Key Highlights & Innovations

1. **Integrated 3D Digital Twin Viewer (Three.js)**
   - High-fidelity 3D viewport streaming `.glb` architectural models with ACESFilmic tone mapping and soft contact shadows.
   - Dynamic 3D POI markers with pulsing floor target rings, category-themed color accents, and billboarded canvas labels.
   - Smooth camera transitions (TWEEN) with instant focus and top-down architectural bird's-eye view toggle.
   - First-person / third-person **Walkthrough Tour** that animates the camera following the computed path in real time.

2. **Obstacle-Aware 2D/3D Pathfinding (8-Way A* + String Pulling)**
   - **Cross-Section Slicing:** Slices 3D models at human torso height ($[Y_{\text{floor}} + 0.2\text{m},\; Y_{\text{floor}} + 1.8\text{m}]$) into a $0.15\text{m}$ occupancy grid.
   - **Euclidean Obstacle Clearance:** Inflates rigid walls and obstacles by an agent radius ($0.3\text{m}$) using a circular Euclidean kernel to prevent avatar clipping.
   - **Admissible Octile Heuristic:** 8-connected grid movement with corner-cutting elimination guards:
     $$h = (|dx - dz| + \sqrt{2} \min(dx, dz)) \times \text{cell\_size}$$
   - **Line-of-Sight Greedy String Pulling:** Raycasts along path waypoints to eliminate jagged grid steps, compressing 50+ raw cells into 4–6 smooth natural segments.
   - **Visual Occupancy Overlay:** Toggle the live 2D navmesh directly onto the 3D floor plane in real time.

3. **Sub-Millisecond Spatial POI Queries (KD-Tree)**
   - In-memory `scipy.spatial.KDTree` indexing over SQLite persistence.
   - $O(\log N)$ radius filtering and k-nearest queries executing in $< 0.5\text{ms}$.
   - Strict venue axis-aligned bounding box ($[X_{min}, X_{max}] \times [Y_{min}, Y_{max}] \times [Z_{min}, Z_{max}]$) validation.

4. **Typo-Tolerant Multi-Field Search (RapidFuzz)**
   - C-optimized Levenshtein token-set scoring matching phonetics, abbreviations, and transposed characters:
     $$\text{Score} = \max(S_{\text{name}} \times 1.00,\; S_{\text{tags}} \times 0.85,\; S_{\text{category}} \times 0.70,\; S_{\text{desc}} \times 0.50)$$
   - Automatically ranks results by match confidence and user distance.

5. **Zero-Hardcode Venue Onboarding (`onboard_venue.py`)**
   - Ingests arbitrary 3D models (`.glb`, `.gltf`, `.ply`, `.obj`), automatically calculates 3D bounding extents, extracts floor planes, synthesizes spawn points, and generates navigation grids.

---

## 🏛️ System Architecture

```
       +-------------------------------------------------------------+
       |                  Three.js Web Frontend                      |
       |  (Free-roam OrbitControls, 3D POI pins, glowing route line, |
       |   typo-tolerant search bar, navmesh overlay, walk tour)     |
       +------------------------------+------------------------------+
                                      |
                      HTTP / REST (JSON & GLB Streams)
                                      |
       +------------------------------v------------------------------+
       |                FastAPI Gateway (Uvicorn)                    |
       | - CORS middleware, X-Process-Time telemetry, error envelope |
       +-------------------------------------------------------------+
                |                       |                     |
      +---------v---------+   +---------v---------+  +--------v-------+
      |   Venue Registry  |   |    Spatial POI    |  |  Occupancy &   |
      |   & Model Server  |   |   Search Engine   |  | Pathfinding A* |
      | (Config-driven)   |   | (KD-Tree + FTS)   |  |  (2D Grid Map) |
      +---------+---------+   +---------+---------+  +--------+-------+
                |                       |                     |
                v                       v                     v
      data/venues/<id>/       data/venues/<id>/      data/venues/<id>/
      - config.json           - nammaspace.db        - navmesh.npz
      - models/scene.glb                             - debug_map.png
```

---

## 📐 Spatial Coordinate Standard

* **Handedness:** Right-handed system (Three.js native standard).
* **Axes:** `+X` = Right (east), `+Y` = Up (vertical height), `+Z` = Forward / Viewer (south).
* **Units:** International System of Units (meters, $1.0\text{ unit} = 1.0\text{ meter}$).
* **Floor Level:** Default reference is at $Y = 0.0\text{m}$.

---

## 🚀 Quickstart & Local Setup

### Prerequisites
* Python 3.11+
* (Optional) Node.js 18+ (if serving frontend via standalone dev server)

### 1. Clone & Set Up Python Environment
```bash
git clone https://github.com/ww7393299-oss/namma-space.git
cd namma-space

# Create virtual environment
python -m venv backend/.venv
# Windows:
backend\.venv\Scripts\activate
# Linux/macOS:
source backend/.venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Run the Application
```bash
# Windows quickstart:
cd backend && run.bat
# Or direct Uvicorn launch:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

* **3D Digital Twin Viewer:** [http://localhost:8000/](http://localhost:8000/) or [http://localhost:8000/viewer](http://localhost:8000/viewer)
* **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **OpenAPI 3.1 JSON Specification:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 🧪 Testing & Verification

Run the comprehensive 44-test test suite covering all phases:
```bash
pytest backend/tests -v
```

Run the end-to-end interactive CLI demonstration pipeline:
```bash
python backend/scripts/demo_pipeline.py
```

---

## 📡 Core API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health, version, and active registered venue count. |
| `GET` | `/venues` | List all registered venues with bounds and dimensions. |
| `GET` | `/venues/{id}` | Detailed venue configuration, camera spawn points, and model stream URL. |
| `POST` | `/venues/reload` | Hot-reloads all venue configurations without downtime. |
| `GET` | `/venues/{id}/pois` | List all POIs or perform KD-tree radius filter (`?x=0&z=0&radius=5`). |
| `POST` | `/venues/{id}/pois` | Register a new POI with bounding-box validation. |
| `GET` | `/venues/{id}/search` | Typo-tolerant search (`?q=wrkstation&user_x=-5&user_z=-3`). |
| `POST` | `/venues/{id}/navigate` | Compute obstacle-aware path (`{ start, goal, smooth_path: true }`). |
| `GET` | `/venues/{id}/navmesh/debug` | Stream visual 2D occupancy grid PNG with obstacle inflation. |

---

## 🚢 Production & Serverless Deployment (Vercel)

The repository includes a battle-tested serverless configuration:
* `vercel.json` maps incoming traffic directly to `@vercel/python` serverless lambdas.
* `api/index.py` handles cold-start SQLite schema initialization and POI seeding into writable `/tmp` cache.
* Lightweight fallback implementations for KD-Tree and string pulling ensure rapid cold starts ($< 1.5\text{s}$) under serverless constraints.

Deploy to Vercel:
```bash
vercel --prod
```

---

## 👥 Engineering Team

* **Vishwananth:** Backend Architecture, Spatial Algorithms, 2D/3D Navigation & Pathfinding
* **Naresh:** Frontend Visualization & Three.js Integration
* **Santosh:** Standard Operating Procedures (SOP), Abstract & System Verification
