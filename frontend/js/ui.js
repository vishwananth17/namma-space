/**
 * NammaSpace 3D - User Interface Controller
 */

export class UIController {
  constructor() {
    // Elements
    this.venueSelect = document.getElementById('venue-select');
    this.backendStatusPill = document.getElementById('backend-status');
    this.backendStatusText = document.getElementById('backend-status-text');
    this.backendLatency = document.getElementById('backend-latency');

    this.searchInput = document.getElementById('search-input');
    this.searchClearBtn = document.getElementById('search-clear-btn');
    this.searchResultsDropdown = document.getElementById('search-results-dropdown');

    this.navDrawer = document.getElementById('nav-drawer');
    this.drawerToggleBtn = document.getElementById('drawer-toggle-btn');
    this.navStartSelect = document.getElementById('nav-start-select');
    this.navGoalSelect = document.getElementById('nav-goal-select');
    this.btnSwapPoints = document.getElementById('btn-swap-points');
    this.btnUseCameraStart = document.getElementById('btn-use-camera-start');
    this.navSmoothToggle = document.getElementById('nav-smooth-toggle');
    this.btnCalculateRoute = document.getElementById('btn-calculate-route');

    this.routeSummary = document.getElementById('route-summary');
    this.metricDistance = document.getElementById('metric-distance');
    this.metricTime = document.getElementById('metric-time');
    this.metricLatency = document.getElementById('metric-latency');
    this.metricWaypoints = document.getElementById('metric-waypoints');
    this.btnStartTour = document.getElementById('btn-start-tour');
    this.btnClearRoute = document.getElementById('btn-clear-route');
    this.waypointsList = document.getElementById('waypoints-list');
    this.quickChipsContainer = document.getElementById('quick-poi-chips');

    this.routeRerouteAlert = document.getElementById('route-reroute-alert');
    this.routeRerouteText = document.getElementById('route-reroute-text');
    this.directionsCount = document.getElementById('directions-count');
    this.directionsList = document.getElementById('directions-list');
    this.btnInjectSpill = document.getElementById('btn-inject-spill');
    this.btnClearHazards = document.getElementById('btn-clear-hazards');
    this.obstacleCountBadge = document.getElementById('obstacle-count-badge');

    this.loadingOverlay = document.getElementById('loading-overlay');
    this.loaderStatus = document.getElementById('loader-status');
    this.loaderProgressFill = document.getElementById('loader-progress-fill');

    this.poiHoverTooltip = document.getElementById('poi-hover-tooltip');
    this.tooltipTitle = document.getElementById('tooltip-title');
    this.tooltipCategory = document.getElementById('tooltip-category');

    this.poiDetailCard = document.getElementById('poi-detail-card');
    this.btnClosePoiCard = document.getElementById('btn-close-poi-card');
    this.poiCardCategory = document.getElementById('poi-card-category');
    this.poiCardTitle = document.getElementById('poi-card-title');
    this.poiCardDescription = document.getElementById('poi-card-description');
    this.poiCardX = document.getElementById('poi-card-x');
    this.poiCardY = document.getElementById('poi-card-y');
    this.poiCardZ = document.getElementById('poi-card-z');
    this.poiCardFloor = document.getElementById('poi-card-floor');
    this.poiCardTags = document.getElementById('poi-card-tags');
    this.btnPoiNavigateTo = document.getElementById('btn-poi-navigate-to');
    this.btnPoiSetStart = document.getElementById('btn-poi-set-start');
    this.btnPoiFocus = document.getElementById('btn-poi-focus');

    this.hudFps = document.getElementById('hud-fps');
    this.hudPoisCount = document.getElementById('hud-pois-count');
    this.hudDimensions = document.getElementById('hud-dimensions');
    this.hudApiLatency = document.getElementById('hud-api-latency');
    this.toastContainer = document.getElementById('toast-container');

    this.btnToggleView = document.getElementById('btn-toggle-view');
    this.btnToggleNavmesh = document.getElementById('btn-toggle-navmesh');
    this.btnResetCamera = document.getElementById('btn-reset-camera');

    this.searchDebounceTimer = null;
    this.activePOI = null;
    this._bindEvents();
  }

  _bindEvents() {
    // Drawer Collapse Toggle
    this.drawerToggleBtn?.addEventListener('click', () => {
      this.navDrawer.classList.toggle('collapsed');
      const isCollapsed = this.navDrawer.classList.contains('collapsed');
      this.drawerToggleBtn.innerHTML = isCollapsed
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>';
    });

    // Close POI Detail Card
    this.btnClosePoiCard?.addEventListener('click', () => {
      this.poiDetailCard.classList.add('hidden');
    });

    // Keyboard shortcut '/' to search
    window.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== this.searchInput) {
        e.preventDefault();
        this.searchInput.focus();
      } else if (e.key === 'Escape') {
        this.hideSearchResults();
        this.poiDetailCard.classList.add('hidden');
      }
    });

    // Clear search
    this.searchClearBtn?.addEventListener('click', () => {
      this.searchInput.value = '';
      this.searchClearBtn.classList.add('hidden');
      this.hideSearchResults();
    });

    // Swap Start and Goal
    this.btnSwapPoints?.addEventListener('click', () => {
      const temp = this.navStartSelect.value;
      this.navStartSelect.value = this.navGoalSelect.value;
      this.navGoalSelect.value = temp;
    });
  }

  setBackendStatus(online, latencyMs = 0) {
    if (online) {
      this.backendStatusText.textContent = 'Backend Online';
      this.backendStatusPill.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      this.backendLatency.textContent = `${latencyMs} ms`;
      this.hudApiLatency.textContent = `${latencyMs} ms`;
    } else {
      this.backendStatusText.textContent = 'Offline / Error';
      this.backendStatusPill.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      this.backendLatency.textContent = 'err';
    }
  }

  showLoading(title, subtitle, progress = 20) {
    this.loadingOverlay.classList.remove('fade-out');
    if (title) this.loadingOverlay.querySelector('.loader-title').textContent = title;
    if (subtitle) this.loaderStatus.textContent = subtitle;
    this.loaderProgressFill.style.width = `${progress}%`;
  }

  hideLoading() {
    this.loaderProgressFill.style.width = '100%';
    setTimeout(() => {
      this.loadingOverlay.classList.add('fade-out');
    }, 250);
  }

  populateVenues(venues, currentVenueId) {
    this.venueSelect.innerHTML = '';
    venues.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = `${v.name} (${v.id})`;
      if (v.id === currentVenueId) opt.selected = true;
      this.venueSelect.appendChild(opt);
    });
  }

  populatePOIs(pois) {
    this.hudPoisCount.textContent = pois.length;

    // Reset dropdowns
    this.navStartSelect.innerHTML = '<option value="">Choose Starting Point...</option>';
    this.navGoalSelect.innerHTML = '<option value="">Choose Destination...</option>';
    this.quickChipsContainer.innerHTML = '';

    pois.forEach((poi) => {
      const opt1 = document.createElement('option');
      opt1.value = poi.id;
      opt1.textContent = `${poi.name} [${poi.category}]`;
      this.navStartSelect.appendChild(opt1);

      const opt2 = document.createElement('option');
      opt2.value = poi.id;
      opt2.textContent = `${poi.name} [${poi.category}]`;
      this.navGoalSelect.appendChild(opt2);

      // Quick Chips (First 6)
      if (this.quickChipsContainer.children.length < 6) {
        const chip = document.createElement('button');
        chip.className = 'poi-chip';
        chip.textContent = poi.name;
        chip.title = `Quick route to ${poi.name}`;
        chip.addEventListener('click', () => {
          this.navGoalSelect.value = poi.id;
          if (!this.navStartSelect.value && pois.length > 1) {
            // default start to first POI or another
            const other = pois.find((p) => p.id !== poi.id);
            if (other) this.navStartSelect.value = other.id;
          }
          this.btnCalculateRoute.click();
        });
        this.quickChipsContainer.appendChild(chip);
      }
    });
  }

  showSearchResults(results, onSelect) {
    this.searchResultsDropdown.innerHTML = '';
    this.searchResultsDropdown.classList.remove('hidden');

    if (!results || results.length === 0) {
      this.searchResultsDropdown.innerHTML = `
        <div class="search-empty-state">No matching locations found. Try another search term.</div>
      `;
      return;
    }

    results.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'search-result-item';
      const distStr = item.distance !== undefined ? ` • ${item.distance.toFixed(1)}m away` : '';
      const matchedFieldStr = item.matched_field ? `via ${item.matched_field}` : '';

      row.innerHTML = `
        <div class="result-main">
          <span class="result-name">${item.name}</span>
          <div class="result-sub">
            <span class="poi-category-badge">${item.category}</span>
            <span>Floor ${item.floor ?? 0}${distStr}</span>
          </div>
        </div>
        <div class="result-meta">
          <span class="match-score-pill">${Math.round(item.score)}%</span>
          <span class="matched-field-tag">${matchedFieldStr}</span>
        </div>
      `;

      row.addEventListener('click', () => {
        this.hideSearchResults();
        if (onSelect) onSelect(item);
      });

      this.searchResultsDropdown.appendChild(row);
    });
  }

  hideSearchResults() {
    this.searchResultsDropdown.classList.add('hidden');
  }

  showPOIDetail(poi, onNavigate, onSetStart, onFocus) {
    this.activePOI = poi;
    this.poiCardCategory.textContent = poi.category || 'Location';
    this.poiCardTitle.textContent = poi.name;
    this.poiCardDescription.textContent = poi.description || 'No additional description provided.';
    this.poiCardX.textContent = poi.position.x.toFixed(2);
    this.poiCardY.textContent = poi.position.y.toFixed(2);
    this.poiCardZ.textContent = poi.position.z.toFixed(2);
    this.poiCardFloor.textContent = poi.floor ?? 0;

    // Tags
    this.poiCardTags.innerHTML = '';
    if (poi.tags && poi.tags.length > 0) {
      poi.tags.forEach((tag) => {
        const pill = document.createElement('span');
        pill.className = 'poi-tag-pill';
        pill.textContent = `#${tag}`;
        this.poiCardTags.appendChild(pill);
      });
    }

    // Actions
    this.btnPoiNavigateTo.onclick = () => {
      this.navGoalSelect.value = poi.id;
      this.navDrawer.classList.remove('collapsed');
      if (onNavigate) onNavigate(poi);
    };

    this.btnPoiSetStart.onclick = () => {
      this.navStartSelect.value = poi.id;
      this.navDrawer.classList.remove('collapsed');
      if (onSetStart) onSetStart(poi);
      this.showToast(`Set '${poi.name}' as route start point.`, 'success');
    };

    this.btnPoiFocus.onclick = () => {
      if (onFocus) onFocus(poi);
    };

    this.poiDetailCard.classList.remove('hidden');
  }

  showRouteSummary(navData) {
    this.routeSummary.classList.remove('hidden');
    this.metricDistance.textContent = `${navData.total_distance_meters.toFixed(1)} m`;
    this.metricTime.textContent = `${navData.estimated_walking_time_seconds.toFixed(0)} s`;
    this.metricLatency.textContent = `${navData.execution_time_ms.toFixed(1)} ms`;
    this.metricWaypoints.textContent = `${navData.total_waypoints} ${navData.path_smoothed ? '(Smoothed)' : ''}`;

    // Dynamic Obstacle Reroute Alert
    if (navData.rerouted_due_to_obstacles) {
      const avoidedStr =
        navData.avoided_obstacles && navData.avoided_obstacles.length > 0
          ? ` (${navData.avoided_obstacles.join(', ')})`
          : '';
      this.routeRerouteText.textContent = `Route safely diverted around active hazard${avoidedStr}!`;
      this.routeRerouteAlert.classList.remove('hidden');
    } else {
      this.routeRerouteAlert.classList.add('hidden');
    }

    // Turn-by-Turn Natural Directions
    this.directionsList.innerHTML = '';
    if (navData.directions && navData.directions.length > 0) {
      this.directionsCount.textContent = `${navData.directions.length} steps`;
      navData.directions.forEach((d) => {
        const card = document.createElement('div');
        card.className = 'direction-step-card';
        card.dataset.stepIndex = d.waypoint_index;

        const landmarkTag = d.nearby_landmark
          ? `<span class="step-landmark">📍 near ${d.nearby_landmark}</span>`
          : '';
        const distTag = d.distance_meters > 0 ? `${d.distance_meters.toFixed(1)}m • ` : '';

        card.innerHTML = `
          <span class="step-num-badge">#${d.step}</span>
          <div class="step-content">
            <span class="step-instruction">${d.instruction}</span>
            <div class="step-meta">
              <span>${distTag}${d.compass_bearing_deg}° ${d.cardinal_direction}</span>
              ${landmarkTag}
            </div>
          </div>
        `;
        this.directionsList.appendChild(card);
      });
    } else {
      this.directionsCount.textContent = '0 steps';
    }

    // Waypoints Timeline
    this.waypointsList.innerHTML = '';
    navData.waypoints.forEach((wp, idx) => {
      const item = document.createElement('div');
      item.className = 'waypoint-item';
      item.innerHTML = `
        <span class="waypoint-num">Step ${idx + 1}</span>
        <span>(${wp.x.toFixed(2)}, ${wp.z.toFixed(2)})</span>
      `;
      this.waypointsList.appendChild(item);
    });
  }

  highlightActiveDirectionStep(wpIndex) {
    const cards = this.directionsList.querySelectorAll('.direction-step-card');
    cards.forEach((card) => {
      const idx = parseInt(card.dataset.stepIndex, 10);
      if (idx === wpIndex) {
        card.classList.add('active-step');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        card.classList.remove('active-step');
      }
    });
  }

  updateObstacleBadge(count) {
    if (this.obstacleCountBadge) {
      this.obstacleCountBadge.textContent = `${count} Active`;
    }
  }

  hideRouteSummary() {
    this.routeSummary.classList.add('hidden');
    this.routeRerouteAlert?.classList.add('hidden');
  }

  showHoverTooltip(poi, clientX, clientY) {
    if (!poi) {
      this.poiHoverTooltip.classList.add('hidden');
      return;
    }
    this.tooltipTitle.textContent = poi.name;
    this.tooltipCategory.textContent = poi.category;
    this.poiHoverTooltip.style.left = `${clientX}px`;
    this.poiHoverTooltip.style.top = `${clientY}px`;
    this.poiHoverTooltip.classList.remove('hidden');
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    this.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  updateHUD(fps, dimensions) {
    this.hudFps.textContent = fps;
    if (dimensions) {
      this.hudDimensions.textContent = `${dimensions.x}m × ${dimensions.z}m`;
    }
  }
}
