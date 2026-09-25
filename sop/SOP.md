# 📋 NammaSpace 3D — Standard Operating Procedure (SOP)

> **Document Version:** 1.0.0  
> **Target Audience:** Operations, Judging Panel, Presenters & Team (Santosh, Vishwananth, Naresh)  
> **Platform:** NammaSpace 3D Indoor Digital Twin System  

---

## 1. Purpose & Scope
This Standard Operating Procedure defines the step-by-step operational workflows for running, demonstrating, onboarding venues, and troubleshooting the NammaSpace 3D digital twin platform during hackathon evaluation rounds.

---

## 2. System Verification & Pre-Flight Checklist

Perform this 60-second verification before any live judging session:

1. **Start Backend Server:**
   ```bash
   cd backend
   run.bat
   # or
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Verify Health Endpoint:**
   - Open [http://localhost:8000/health](http://localhost:8000/health) in browser.
   - Confirm JSON response:
     ```json
     {
       "status": "healthy",
       "app": "NammaSpace 3D Digital Twin Backend",
       "version": "0.1.0",
       "registered_venues_count": 2,
       "venue_ids": ["iitb_hall", "sample_lab"]
     }
     ```
3. **Execute Automated Pipeline Test:**
   ```bash
   python scripts/demo_pipeline.py
   ```
   - Must output: `DEMO COMPLETED SUCCESSFULLY! ALL SYSTEMS GO FOR HACKATHON.`
4. **Open 3D Digital Twin Viewer:**
   - Navigate to [http://localhost:8000/](http://localhost:8000/).
   - Verify that the 3D model loads, pins appear, and the latency pill reads `< 15ms`.

---

## 3. Live Demonstration Protocol (3-Minute Judging Walkthrough)

Follow this exact sequence to demonstrate maximum technical depth:

### Step 1: 3D Digital Twin & Spatial Navigation (45 Seconds)
- Open [http://localhost:8000/](http://localhost:8000/).
- Show the 3D architectural model with OrbitControls (pan, tilt, zoom).
- Toggle between **3D Perspective** and **Top-Down Architectural View** via the top toolbar button.
- Click any floating 3D pin (e.g. `Workstation Alpha`) to showcase smooth camera gliding (TWEEN) and the slide-in POI detail card showing metric coordinates $(X, Y, Z)$ and tags.

### Step 2: Typo-Tolerant Multi-Field Search (45 Seconds)
- Press `/` or click into the floating search bar.
- Type intentional typos into the search input:
  - `wrkstation` $\rightarrow$ Instantly matches **Workstation Alpha (GPU Cluster)** (81% match via name).
  - `cofee` $\rightarrow$ Instantly matches **Refreshment & Coffee Corner** (77% match via tags).
  - `bmbulab` $\rightarrow$ Instantly matches **Bambu Lab 3D Printing Hub** (77% match via name).
- Emphasize sub-10ms response latency displayed on the HUD.
- Click a search result to fly the camera directly to that equipment in 3D.

### Step 3: Obstacle-Aware A* Pathfinding & Walkthrough (60 Seconds)
- In the left navigation drawer:
  - Select Origin: `Workstation Alpha` (or click `Use Camera Eye`).
  - Select Destination: `Refreshment & Coffee Corner`.
  - Ensure `Line-of-Sight Smoothing (Raycasting)` is checked.
- Click **Compute Optimal Path**:
  - Point out the glowing neon cyan 3D pathline with directional pulses and waypoint nodes.
  - Highlight the metrics: Distance ($18.5\text{m}$), Walking Time ($15.4\text{s}$), and A* compute time ($< 25\text{ms}$).
- Click **Walkthrough Tour**:
  - The camera smoothly glides through the venue following the computed waypoints at realistic walking speed.
- Toggle **Navmesh Button**:
  - The 2D obstacle-inflation occupancy grid is projected directly onto the floor, proving to judges that the avatar avoids all walls and furniture with a $0.3\text{m}$ clearance buffer.

---

## 4. Live Venue Onboarding Procedure (Round 3 Evaluation)

When judges provide a new 3D model file (e.g., `iitb_auditorium.glb` or `.obj`):

1. **Place Model in Ingestion Directory:**
   ```bash
   backend/data/venues/new_venue/models/scene.glb
   ```
2. **Run the Automated Onboarder:**
   ```bash
   python backend/scripts/onboard_venue.py \
       --id new_venue \
       --name "IIT Bombay Auditorium" \
       --model backend/data/venues/new_venue/models/scene.glb \
       --resolution 0.15 \
       --agent-radius 0.30
   ```
   The script automatically:
   - Computes 3D axis-aligned bounding box.
   - Identifies floor height plane.
   - Slices geometry and builds the 2D occupancy grid with obstacle inflation.
   - Synthesizes Three.js camera spawn orientation.
   - Generates `config.json` and `debug_map.png`.
3. **Hot-Reload Venue Registry:**
   - In browser or terminal, execute:
     ```bash
     curl -X POST http://localhost:8000/venues/reload
     ```
   - The new venue appears immediately in the frontend venue selector dropdown without restarting the server!

---

## 5. Troubleshooting & Fallback Procedures

| Symptom | Cause | Remediation |
|---|---|---|
| Port 8000 in use | Stray process from previous run | Run `taskkill /F /IM python.exe` or change port to 8001 (`PORT=8001 run.bat`). |
| 3D Model not rendering | WebGL context issue or unsupported browser | Confirm hardware acceleration is on in Chrome (`chrome://settings/system`). |
| "Origin and Destination identical" | Same POI selected in both fields | Pick distinct locations or click another POI chip. |
| Offline / Backend Error badge | Backend server crashed or network disconnected | Check terminal output for stack trace; restart via `run.bat`. |

---

## 6. Document Sign-Off
- **Prepared By:** Santosh & Vishwananth
- **Approved For:** Hackathon Live Demonstrations & Judging Submissions
