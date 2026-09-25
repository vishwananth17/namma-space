/**
 * NammaSpace 3D - Main Application Entrypoint
 */

import { api } from './api.js';
import { Viewer3D } from './viewer3d.js';
import { UIController } from './ui.js';

class App {
  constructor() {
    this.canvas = document.getElementById('webgl-canvas');
    this.viewer = new Viewer3D(this.canvas);
    this.ui = new UIController();

    this.currentVenueId = 'sample_lab';
    this.currentVenueData = null;
    this.pois = [];
    this.activeRoute = null;
    this.navmeshVisible = false;

    this._setupEventHandlers();
  }

  async init() {
    this.ui.showLoading('Connecting to NammaSpace Backend...', 'Checking spatial gateway...', 25);

    try {
      // 1. Health Check
      const health = await api.checkHealth();
      this.ui.setBackendStatus(true, api.lastLatencyMs);

      // 2. Fetch Venues
      this.ui.showLoading('Loading Registered Venues...', 'Reading venue configurations...', 50);
      const venues = await api.listVenues();
      this.ui.populateVenues(venues, this.currentVenueId);

      // 3. Load Default Venue
      await this.loadVenue(this.currentVenueId);
      this.ui.showToast(`Connected to NammaSpace Digital Twin (${health.app})`, 'success');
    } catch (err) {
      console.error('Initialization failed:', err);
      this.ui.setBackendStatus(false);
      this.ui.showToast(`Failed to connect to backend: ${err.message}`, 'error');
      // Still load fallback sample lab if offline
      await this.loadVenue(this.currentVenueId);
    } finally {
      this.ui.hideLoading();
      this._startTelemetryTicker();
    }
  }

  async loadVenue(venueId) {
    this.currentVenueId = venueId;
    this.ui.showLoading(`Loading Venue: ${venueId}`, 'Fetching 3D geometry & spatial index...', 40);

    try {
      // 1. Get Venue Metadata
      const venue = await api.getVenue(venueId);
      this.currentVenueData = venue;

      // 2. Load 3D Asset
      this.ui.showLoading(`Streaming 3D Mesh...`, 'Streaming binary GLB model...', 70);
      const modelUrl = api.getModelUrl(venueId, venue.model_file || 'models/sample_room.glb');
      await this.viewer.loadVenue(venue, modelUrl);

      // 3. Load POIs
      this.ui.showLoading(`Fetching POIs...`, 'Building in-memory KD-Tree spatial pins...', 90);
      const pois = await api.getPOIs(venueId);
      this.pois = pois;
      this.viewer.renderPOIs(pois);
      this.ui.populatePOIs(pois);

      // 4. Update HUD
      if (venue.bounds?.dimensions) {
        this.ui.updateHUD(this.viewer.fps, venue.bounds.dimensions);
      }

      this.ui.clearSearch?.();
      this.ui.hideRouteSummary();
      this.activeRoute = null;
      this.navmeshVisible = false;
    } catch (err) {
      console.error(`Error loading venue ${venueId}:`, err);
      this.ui.showToast(`Failed to load venue '${venueId}': ${err.message}`, 'error');
    } finally {
      this.ui.hideLoading();
    }
  }

  _setupEventHandlers() {
    // Venue Switching
    this.ui.venueSelect.addEventListener('change', async (e) => {
      const selected = e.target.value;
      if (selected && selected !== this.currentVenueId) {
        await this.loadVenue(selected);
      }
    });

    // 3D POI Hover & Click
    this.viewer.onPOIHover = (poi, clientX, clientY) => {
      this.ui.showHoverTooltip(poi, clientX, clientY);
    };

    this.viewer.onPOIClick = (poi) => {
      this.ui.showPOIDetail(
        poi,
        (targetPoi) => this._triggerRoute(null, targetPoi.id),
        (startPoi) => {
          this.ui.navStartSelect.value = startPoi.id;
        },
        (focusPoi) => this.viewer.selectPOI(focusPoi.id)
      );
    };

    // Typo-Tolerant Search with Debounce
    this.ui.searchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (!q) {
        this.ui.searchClearBtn.classList.add('hidden');
        this.ui.hideSearchResults();
        return;
      }
      this.ui.searchClearBtn.classList.remove('hidden');

      clearTimeout(this.ui.searchDebounceTimer);
      this.ui.searchDebounceTimer = setTimeout(async () => {
        try {
          const userPos = {
            x: this.viewer.camera.position.x,
            z: this.viewer.camera.position.z
          };
          const data = await api.searchPOIs(this.currentVenueId, q, userPos);
          this.ui.setBackendStatus(true, api.lastLatencyMs);

          this.ui.showSearchResults(data.results, (selectedItem) => {
            this.viewer.selectPOI(selectedItem.id);
            const fullPOI = this.pois.find((p) => p.id === selectedItem.id) || selectedItem;
            this.ui.showPOIDetail(
              fullPOI,
              (target) => this._triggerRoute(null, target.id),
              (start) => {
                this.ui.navStartSelect.value = start.id;
              },
              (focus) => this.viewer.selectPOI(focus.id)
            );
          });
        } catch (err) {
          console.error('Search error:', err);
        }
      }, 150);
    });

    // Calculate Navigation Route
    this.ui.btnCalculateRoute.addEventListener('click', async () => {
      const start = this.ui.navStartSelect.value;
      const goal = this.ui.navGoalSelect.value;
      if (!start || !goal) {
        this.ui.showToast('Please select both Origin and Destination.', 'error');
        return;
      }
      if (start === goal) {
        this.ui.showToast('Origin and Destination cannot be identical.', 'error');
        return;
      }
      await this._triggerRoute(start, goal);
    });

    // Use Camera Position as Start
    this.ui.btnUseCameraStart?.addEventListener('click', () => {
      const camPos = this.viewer.camera.position;
      const customStart = `cam:${camPos.x.toFixed(2)},${camPos.z.toFixed(2)}`;
      // Check if custom option already in select
      let opt = Array.from(this.ui.navStartSelect.options).find((o) => o.value.startsWith('cam:'));
      if (!opt) {
        opt = document.createElement('option');
        this.ui.navStartSelect.insertBefore(opt, this.ui.navStartSelect.children[1]);
      }
      opt.value = `${camPos.x.toFixed(2)},${camPos.z.toFixed(2)}`;
      opt.textContent = `📍 Camera Eye (${camPos.x.toFixed(1)}m, ${camPos.z.toFixed(1)}m)`;
      opt.selected = true;
      this.ui.showToast('Used current 3D camera coordinates as route start.', 'success');
    });

    // Start Walkthrough Tour
    this.ui.btnStartTour.addEventListener('click', () => {
      if (!this.activeRoute?.waypoints) return;
      this.viewer.startWalkTour(this.activeRoute.waypoints, () => {
        this.ui.showToast('Walkthrough tour completed!', 'success');
      });
    });

    // Clear Route
    this.ui.btnClearRoute.addEventListener('click', () => {
      this.viewer.clearPath();
      this.ui.hideRouteSummary();
      this.activeRoute = null;
    });

    // Toggle 3D / Top-Down View
    this.ui.btnToggleView.addEventListener('click', () => {
      const isTopDown = this.viewer.toggleViewMode();
      this.ui.btnToggleView.querySelector('.btn-text').textContent = isTopDown ? '3D View' : 'Top-Down';
    });

    // Toggle Navmesh Overlay
    this.ui.btnToggleNavmesh.addEventListener('click', () => {
      this.navmeshVisible = !this.navmeshVisible;
      const debugUrl = api.getNavmeshDebugUrl(this.currentVenueId);
      this.viewer.toggleNavmeshOverlay(this.navmeshVisible, this.currentVenueId, debugUrl);
      this.ui.btnToggleNavmesh.classList.toggle('nav-btn-accent', this.navmeshVisible);
      this.ui.showToast(
        this.navmeshVisible
          ? 'Occupancy grid & clearance overlay enabled.'
          : 'Occupancy grid overlay hidden.',
        'info'
      );
    });

    // Reset Camera
    this.ui.btnResetCamera.addEventListener('click', () => {
      this.viewer.resetCamera();
    });
  }

  async _triggerRoute(startId, goalId) {
    const start = startId || this.ui.navStartSelect.value;
    const goal = goalId || this.ui.navGoalSelect.value;
    const smooth = this.ui.navSmoothToggle.checked;

    if (!start || !goal) return;

    this.ui.btnCalculateRoute.disabled = true;
    this.ui.btnCalculateRoute.innerHTML = '<span>Calculating A* Path...</span>';

    try {
      const data = await api.navigate(this.currentVenueId, start, goal, smooth);
      this.activeRoute = data;
      this.ui.setBackendStatus(true, api.lastLatencyMs);

      // Render glowing 3D polyline
      this.viewer.renderPath(data.waypoints);

      // Show summary in drawer
      this.ui.showRouteSummary(data);
      this.ui.showToast(
        `Path found! Distance: ${data.total_distance_meters.toFixed(1)}m in ${data.execution_time_ms.toFixed(1)}ms`,
        'success'
      );
    } catch (err) {
      console.error('Navigation error:', err);
      this.ui.showToast(`Pathfinding failed: ${err.message}`, 'error');
    } finally {
      this.ui.btnCalculateRoute.disabled = false;
      this.ui.btnCalculateRoute.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="6" y1="3" x2="6" y2="15"></line>
          <circle cx="18" cy="6" r="3"></circle>
          <circle cx="6" cy="18" r="3"></circle>
          <path d="M18 9a9 9 0 0 1-9 9"></path>
        </svg>
        <span>Compute Optimal Path</span>
      `;
    }
  }

  _startTelemetryTicker() {
    setInterval(() => {
      this.ui.updateHUD(this.viewer.fps);
    }, 1000);
  }
}

// Start app on DOMContentLoaded
window.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});
