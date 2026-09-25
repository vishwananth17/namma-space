/**
 * NammaSpace 3D — Google Maps Indoor Application Entrypoint
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
    this.currentFloor = 0;

    this._setupEventHandlers();
  }

  async init() {
    this.ui.showLoading('Locating Indoor Space...', 'Connecting to spatial twin engine...', 25);

    try {
      // 1. Health check
      await api.checkHealth();

      // 2. Fetch venues
      this.ui.showLoading('Loading Registered Venues...', 'Fetching 3D floor configurations...', 50);
      const venues = await api.listVenues();
      this.ui.populateVenues(venues, this.currentVenueId);

      // 3. Load default venue
      await this.loadVenue(this.currentVenueId);
      this.ui.showToast('NammaSpace Indoor Maps Ready 📍', 'success');
    } catch (err) {
      console.error('Initialization failed:', err);
      this.ui.showToast(`Backend connection notice: ${err.message}`, 'error');
      // Load fallback venue geometry
      await this.loadVenue(this.currentVenueId);
    } finally {
      this.ui.hideLoading();
    }
  }

  async loadVenue(venueId) {
    this.currentVenueId = venueId;
    this.ui.showLoading(`Loading ${venueId}`, 'Loading 3D mesh & spatial graph...', 40);

    try {
      // 1. Venue metadata
      const venue = await api.getVenue(venueId);
      this.currentVenueData = venue;

      // 2. 3D Asset
      this.ui.showLoading('Rendering 3D Twin...', 'Loading geometry & lighting...', 70);
      const modelUrl = api.getModelUrl(venueId, venue.model_file || 'models/sample_room.glb');
      await this.viewer.loadVenue(venue, modelUrl);

      // 3. Load POIs
      this.ui.showLoading('Pinning Indoor POIs...', 'Rendering Google Maps indoor markers...', 85);
      const pois = await api.getPOIs(venueId);
      this.pois = pois;
      this.viewer.renderPOIs(pois);
      this.ui.populatePOIs(pois);

      // 4. Load Dynamic Obstacles
      const obstacles = await api.listObstacles(venueId);
      this.viewer.renderObstacles(obstacles);

      // Reset state
      this.ui.hideTripBar();
      this.ui.hidePlaceSheet();
      this.viewer.clearPath();
      this.activeRoute = null;
    } catch (err) {
      console.error(`Error loading venue ${venueId}:`, err);
      this.ui.showToast(`Failed to load venue: ${err.message}`, 'error');
    } finally {
      this.ui.hideLoading();
    }
  }

  _setupEventHandlers() {
    // 1. Venue Selector
    this.ui.venueSelect?.addEventListener('change', async (e) => {
      const selected = e.target.value;
      if (selected && selected !== this.currentVenueId) {
        await this.loadVenue(selected);
      }
    });

    // 2. 3D Hover & Click Handlers
    this.viewer.onPOIHover = (poi, clientX, clientY) => {
      this.ui.showHoverTooltip(poi, clientX, clientY);
    };

    this.viewer.onPOIClick = (poi) => {
      this.ui.showPlaceSheet(
        poi,
        // On Directions Click:
        (destPoi) => {
          this.ui.navGoalSelect.value = destPoi.id;
          this.ui.navStartSelect.value = 'user_pos';
          this._triggerRoute();
        },
        // On Set Start Click:
        (startPoi) => {
          this.ui.navStartSelect.value = startPoi.id;
        },
        // On Look At Click:
        (focusPoi) => {
          this.viewer.selectPOI(focusPoi.id);
        }
      );
    };

    // 3. Floor Click -> Move Blue Dot
    this.viewer.onFloorClick = (pt) => {
      this.ui.showToast(`User location updated: (${pt.x.toFixed(1)}m, ${pt.z.toFixed(1)}m)`, 'info');
      // If start is set to user_pos and active route exists, auto-recalculate
      if (this.ui.navStartSelect.value === 'user_pos' && this.ui.navGoalSelect.value) {
        this._triggerRoute();
      }
    };

    // 4. Category Exploration Chips (Desks, Coffee, Lab, First Aid, Exits)
    this.ui.categoryChips.forEach((chip) => {
      chip.addEventListener('click', () => {
        const category = chip.getAttribute('data-category');
        this.ui.categoryChips.forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');

        const matching = this.pois.filter((p) => p.category === category);
        if (matching.length > 0) {
          this.ui.showSearchResults(
            matching.map((p) => ({
              id: p.id,
              name: p.name,
              category: p.category,
              floor: p.floor,
              score: 100,
              matched_field: 'category'
            })),
            (selectedItem) => {
              const fullPOI = this.pois.find((p) => p.id === selectedItem.id);
              if (fullPOI) {
                this.viewer.selectPOI(fullPOI.id);
                this.viewer.onPOIClick(fullPOI);
              }
            }
          );
          // Fly to first match
          this.viewer.selectPOI(matching[0].id);
          this.ui.showToast(`Found ${matching.length} location(s) in '${category}'`, 'info');
        } else {
          this.ui.showToast(`No locations found in '${category}'`, 'info');
        }
      });
    });

    // 5. Typo-Tolerant Search
    this.ui.searchInput?.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (!q) {
        this.ui.searchClearBtn?.classList.add('hidden');
        this.ui.hideSearchResults();
        return;
      }
      this.ui.searchClearBtn?.classList.remove('hidden');

      clearTimeout(this.ui.searchDebounceTimer);
      this.ui.searchDebounceTimer = setTimeout(async () => {
        try {
          const userPos = { x: this.viewer.userPos.x, z: this.viewer.userPos.z };
          const data = await api.searchPOIs(this.currentVenueId, q, userPos);
          this.ui.showSearchResults(data.results, (selectedItem) => {
            const fullPOI = this.pois.find((p) => p.id === selectedItem.id) || selectedItem;
            this.viewer.selectPOI(fullPOI.id);
            this.viewer.onPOIClick(fullPOI);
          });
        } catch (err) {
          console.error('Search error:', err);
        }
      }, 150);
    });

    // 6. Calculate Route Button (in Directions Panel)
    this.ui.btnCalculateRoute?.addEventListener('click', async () => {
      await this._triggerRoute();
    });

    // 7. Start / Pause Walking Navigation (Google Maps Turn-by-Turn Experience)
    this.ui.btnStartNavigation?.addEventListener('click', () => {
      if (!this.activeRoute?.waypoints) return;

      if (this.viewer.navigationActive) {
        // Pause/stop
        this.viewer.stopNavigation();
        this.ui.setNavigationActive(false);
        this.ui.hideNavigationBanner();
        this.ui.showToast('Indoor navigation paused.', 'info');
      } else {
        // Start live navigation
        this.ui.setNavigationActive(true);
        this.ui.directionsPanel?.classList.add('hidden'); // Minimize panel for full 3D view
        this.ui.hidePlaceSheet();

        const waypoints = this.activeRoute.waypoints;
        const directions = this.activeRoute.directions || [];

        this.viewer.startNavigation(
          waypoints,
          (wpIndex) => {
            // Find current direction step matching or closest to this waypoint index
            const stepIdx = directions.findIndex((d) => d.waypoint_index >= wpIndex);
            const currentStep = directions[stepIdx >= 0 ? stepIdx : directions.length - 1];
            const nextStep = directions[stepIdx + 1] || null;

            if (currentStep) {
              this.ui.showNavigationBanner(currentStep, nextStep);
              this.ui.highlightActiveDirectionStep(currentStep.waypoint_index);
            }
          },
          () => {
            // Reached destination
            this.ui.setNavigationActive(false);
            this.ui.showNavigationBanner(
              { distance_meters: 0, instruction: 'You have arrived at your indoor destination! 📍' },
              null
            );
            this.ui.showToast('You have arrived at your indoor destination!', 'success');
          }
        );
      }
    });

    // 8. Exit Route Button
    this.ui.btnExitNavigation?.addEventListener('click', () => {
      this.viewer.stopNavigation();
      this.viewer.clearPath();
      this.ui.hideTripBar();
      this.ui.hideNavigationBanner();
      this.ui.directionsStepContainer?.classList.add('hidden');
      this.activeRoute = null;
      this.ui.showToast('Exited indoor navigation.', 'info');
    });

    // 9. Floating Control: Re-center on User Blue Dot
    this.ui.btnRecenterUser?.addEventListener('click', () => {
      this.viewer.recenterOnUser();
      this.ui.showToast('Re-centered on your indoor position.', 'info');
    });

    // 10. Floating Control: Compass Re-orient North
    this.ui.btnCompass?.addEventListener('click', () => {
      this.viewer.resetNorth();
      this.ui.showToast('Oriented North.', 'info');
    });

    // 11. Floating Control: 2D / 3D Tilt Toggle
    this.ui.btnToggleView?.addEventListener('click', () => {
      const isTopDown = this.viewer.toggleViewMode();
      this.ui.viewModeLabel.textContent = isTopDown ? '2D' : '3D';
      this.ui.showToast(isTopDown ? 'Switched to 2D Top-Down View' : 'Switched to 3D Perspective View', 'info');
    });

    // 12. Floating Control: Navmesh Toggle
    this.ui.btnToggleNavmesh?.addEventListener('click', () => {
      this.navmeshVisible = !this.navmeshVisible;
      const debugUrl = api.getNavmeshDebugUrl(this.currentVenueId);
      this.viewer.toggleNavmeshOverlay(this.navmeshVisible, this.currentVenueId, debugUrl);
      this.ui.btnToggleNavmesh.classList.toggle('active', this.navmeshVisible);
      this.ui.showToast(
        this.navmeshVisible ? 'Floor walkability grid overlay visible.' : 'Walkability grid overlay hidden.',
        'info'
      );
    });

    // 13. Floor Level Switching (L1 / L2)
    this.ui.floorButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        this.ui.floorButtons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const floor = parseInt(btn.getAttribute('data-floor') || '0', 10);
        this.currentFloor = floor;
        this.ui.showToast(`Switched to Floor ${floor === 1 ? 'L2' : 'L1'}`, 'info');
      });
    });

    // 14. Dynamic Hazard Injection (Simulate Spill / Reroute)
    this.ui.btnInjectSpill?.addEventListener('click', async () => {
      let obsX = 0.0;
      let obsZ = 0.5;

      // Place hazard directly along current active route if available!
      if (this.activeRoute?.waypoints?.length > 2) {
        const midIdx = Math.floor(this.activeRoute.waypoints.length / 2);
        const midWp = this.activeRoute.waypoints[midIdx];
        obsX = midWp.x;
        obsZ = midWp.z;
      }

      try {
        await api.createObstacle(this.currentVenueId, {
          name: 'Liquid Floor Spill Hazard',
          x: obsX,
          z: obsZ,
          radius: 1.1
        });

        const obstacles = await api.listObstacles(this.currentVenueId);
        this.viewer.renderObstacles(obstacles);
        this.ui.showToast('⚠️ Obstacle placed! Recalculating path...', 'info');

        // Automatically recalculate route with active hazard avoidance
        if (this.ui.navGoalSelect.value) {
          await this._triggerRoute();
        }
      } catch (err) {
        this.ui.showToast(`Failed to place hazard: ${err.message}`, 'error');
      }
    });
  }

  async _triggerRoute() {
    const rawStart = this.ui.navStartSelect.value;
    const goal = this.ui.navGoalSelect.value;

    if (!goal) {
      this.ui.showToast('Please select a destination.', 'error');
      return;
    }

    let startPayload;
    if (!rawStart || rawStart === 'user_pos') {
      startPayload = { x: this.viewer.userPos.x, y: 0.1, z: this.viewer.userPos.z };
    } else {
      startPayload = rawStart;
    }

    this.ui.btnCalculateRoute.disabled = true;
    this.ui.btnCalculateRoute.innerHTML = '<span>Finding Best Indoor Route...</span>';

    try {
      const data = await api.navigate(this.currentVenueId, startPayload, goal, true);
      this.activeRoute = data;

      // Render 3D Google Maps vibrant blue route line and 📍 destination pin
      this.viewer.renderPath(data.waypoints);

      // Display summary in directions accordion and bottom trip bar
      this.ui.showRouteSummary(data);

      this.ui.showToast(
        `Route calculated: ${data.total_distance_meters.toFixed(1)}m in ${data.estimated_walking_time_seconds.toFixed(0)}s`,
        'success'
      );
    } catch (err) {
      console.error('Route error:', err);
      this.ui.showToast(`Pathfinding error: ${err.message}`, 'error');
    } finally {
      this.ui.btnCalculateRoute.disabled = false;
      this.ui.btnCalculateRoute.innerHTML = '<span>Find Indoor Route</span>';
    }
  }
}

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});
