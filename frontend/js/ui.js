/**
 * NammaSpace 3D — Google Maps Indoor User Interface Controller
 */

export class UIController {
  constructor() {
    // Top Bar & Search
    this.searchInput = document.getElementById('search-input');
    this.searchClearBtn = document.getElementById('search-clear-btn');
    this.searchResultsDropdown = document.getElementById('search-results-dropdown');
    this.btnOpenDirections = document.getElementById('btn-open-directions');
    this.categoryChips = document.querySelectorAll('.gmaps-chip');

    // Directions Panel
    this.directionsPanel = document.getElementById('directions-panel');
    this.btnCloseDirections = document.getElementById('btn-close-directions');
    this.navStartSelect = document.getElementById('nav-start-select');
    this.navGoalSelect = document.getElementById('nav-goal-select');
    this.btnSwapPoints = document.getElementById('btn-swap-points');
    this.btnCalculateRoute = document.getElementById('btn-calculate-route');
    this.directionsStepContainer = document.getElementById('directions-step-container');
    this.routeTimeVal = document.getElementById('route-time-val');
    this.routeDistVal = document.getElementById('route-dist-val');
    this.routeLatencyBadge = document.getElementById('route-latency-badge');
    this.routeRerouteAlert = document.getElementById('route-reroute-alert');
    this.directionsList = document.getElementById('directions-list');

    // Active Navigation Green Banner (Google Maps Standard)
    this.activeNavBanner = document.getElementById('active-navigation-banner');
    this.navBannerIcon = document.getElementById('nav-banner-icon');
    this.navBannerDistance = document.getElementById('nav-banner-distance');
    this.navBannerInstruction = document.getElementById('nav-banner-instruction');
    this.navBannerNext = document.getElementById('nav-banner-next');
    this.btnToggleVoice = document.getElementById('btn-toggle-voice');
    this.voiceIcon = document.getElementById('voice-icon');
    this.voiceEnabled = true;

    // Bottom Trip Bar
    this.gmapsTripBar = document.getElementById('gmaps-trip-bar');
    this.tripTime = document.getElementById('trip-time');
    this.tripDistance = document.getElementById('trip-distance');
    this.tripStepsCount = document.getElementById('trip-steps-count');
    this.btnStartNavigation = document.getElementById('btn-start-navigation');
    this.navBtnText = document.getElementById('nav-btn-text');
    this.btnExitNavigation = document.getElementById('btn-exit-navigation');

    // Place Details Sheet
    this.gmapsPlaceSheet = document.getElementById('gmaps-place-sheet');
    this.btnClosePlaceSheet = document.getElementById('btn-close-place-sheet');
    this.placeCategory = document.getElementById('place-category');
    this.placeTitle = document.getElementById('place-title');
    this.placeDescription = document.getElementById('place-description');
    this.placeCoords = document.getElementById('place-coords');
    this.placeFloor = document.getElementById('place-floor');
    this.placeTags = document.getElementById('place-tags');
    this.btnPlaceDirections = document.getElementById('btn-place-directions');
    this.btnPlaceSetStart = document.getElementById('btn-place-set-start');
    this.btnPlaceFocus = document.getElementById('btn-place-focus');

    // Floating Controls
    this.venueSelect = document.getElementById('venue-select');
    this.btnCompass = document.getElementById('btn-compass');
    this.compassNeedle = document.getElementById('compass-needle');
    this.btnToggleView = document.getElementById('btn-toggle-view');
    this.viewModeLabel = document.getElementById('view-mode-label');
    this.btnToggleNavmesh = document.getElementById('btn-toggle-navmesh');
    this.btnRecenterUser = document.getElementById('btn-recenter-user');
    this.btnLiveTracking = document.getElementById('btn-live-tracking');
    this.trackingIcon = document.getElementById('tracking-icon');
    this.liveTrackingActive = false;
    this.floorButtons = document.querySelectorAll('.floor-btn');
    this.btnInjectSpill = document.getElementById('btn-inject-spill');

    // Tooltip, Loader & Toasts
    this.loadingOverlay = document.getElementById('loading-overlay');
    this.loaderStatus = document.getElementById('loader-status');
    this.loaderProgressFill = document.getElementById('loader-progress-fill');
    this.poiHoverTooltip = document.getElementById('poi-hover-tooltip');
    this.tooltipTitle = document.getElementById('tooltip-title');
    this.tooltipCategory = document.getElementById('tooltip-category');
    this.toastContainer = document.getElementById('toast-container');

    // Internal state
    this.searchDebounceTimer = null;
    this.activePOI = null;
    this.navigating = false;

    this._bindEvents();
  }

  _bindEvents() {
    // Open / Close Directions Panel
    this.btnOpenDirections?.addEventListener('click', () => {
      this.directionsPanel?.classList.toggle('hidden');
      if (!this.directionsPanel?.classList.contains('hidden')) {
        this.hidePlaceSheet();
      }
    });

    this.btnCloseDirections?.addEventListener('click', () => {
      this.directionsPanel?.classList.add('hidden');
    });

    // Close Place Sheet
    this.btnClosePlaceSheet?.addEventListener('click', () => {
      this.hidePlaceSheet();
    });

    // Clear Search Input
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

    // Voice Navigation Mute/Unmute
    this.btnToggleVoice?.addEventListener('click', () => {
      this.voiceEnabled = !this.voiceEnabled;
      this.voiceIcon.textContent = this.voiceEnabled ? '🔊' : '🔇';
      this.showToast(this.voiceEnabled ? 'Voice navigation unmuted' : 'Voice navigation muted', 'info');
      if (!this.voiceEnabled && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    });

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== this.searchInput) {
        e.preventDefault();
        this.searchInput?.focus();
      } else if (e.key === 'Escape') {
        this.hideSearchResults();
        this.hidePlaceSheet();
      }
    });
  }

  // --- Voice Synthesis (Google Maps style) ---
  speakInstruction(text) {
    if (!this.voiceEnabled || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.lang = 'en-US';
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('Speech synthesis error:', e);
    }
  }

  // --- Green Top Navigation Banner ---
  showNavigationBanner(step, nextStep) {
    this.activeNavBanner.classList.remove('hidden');
    const distText = step.distance_meters > 0 ? `In ${step.distance_meters.toFixed(0)} m` : 'Arrived';
    this.navBannerDistance.textContent = distText;
    this.navBannerInstruction.textContent = step.instruction;

    if (nextStep) {
      this.navBannerNext.textContent = `Then: ${nextStep.instruction}`;
      this.navBannerNext.classList.remove('hidden');
    } else {
      this.navBannerNext.classList.add('hidden');
    }

    this.speakInstruction(step.instruction);
  }

  hideNavigationBanner() {
    this.activeNavBanner.classList.add('hidden');
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }

  // --- Bottom Trip Bar ---
  showTripBar(timeSec, distanceMeters, stepCount) {
    this.gmapsTripBar.classList.remove('hidden');
    const mins = Math.floor(timeSec / 60);
    const secs = Math.round(timeSec % 60);
    this.tripTime.textContent = mins > 0 ? `${mins} min ${secs} s` : `${secs} sec`;
    this.tripDistance.textContent = `${distanceMeters.toFixed(1)} m`;
    this.tripStepsCount.textContent = `${stepCount} steps`;
    this.setNavigationActive(false);
  }

  hideTripBar() {
    this.gmapsTripBar.classList.add('hidden');
    this.hideNavigationBanner();
  }

  setNavigationActive(active) {
    this.navigating = active;
    if (active) {
      this.navBtnText.textContent = 'Pause';
      this.btnStartNavigation.classList.add('nav-running');
    } else {
      this.navBtnText.textContent = 'Start';
      this.btnStartNavigation.classList.remove('nav-running');
    }
  }

  setLiveTrackingActive(active) {
    this.liveTrackingActive = active;
    if (this.btnLiveTracking) {
      this.btnLiveTracking.classList.toggle('active', active);
      this.btnLiveTracking.classList.toggle('tracking-pulse', active);
    }
    if (this.trackingIcon) {
      this.trackingIcon.textContent = active ? '🟢' : '🚶';
    }
    this.showToast(
      active
        ? '🚶 Live Pedestrian Tracking active: walk with your phone or press WASD/Arrows!'
        : 'Live Pedestrian Tracking paused.',
      'info'
    );
  }

  // --- Loading Screen ---
  showLoading(title, subtitle, progress = 20) {
    this.loadingOverlay?.classList.remove('fade-out');
    if (title && this.loadingOverlay?.querySelector('.loader-title')) {
      this.loadingOverlay.querySelector('.loader-title').textContent = title;
    }
    if (subtitle && this.loaderStatus) {
      this.loaderStatus.textContent = subtitle;
    }
    if (this.loaderProgressFill) {
      this.loaderProgressFill.style.width = `${progress}%`;
    }
  }

  hideLoading() {
    if (this.loaderProgressFill) this.loaderProgressFill.style.width = '100%';
    setTimeout(() => {
      this.loadingOverlay?.classList.add('fade-out');
    }, 250);
  }

  // --- Venue & POI Population ---
  populateVenues(venues, currentVenueId) {
    if (!this.venueSelect) return;
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
    // Reset dropdowns
    this.navStartSelect.innerHTML = '<option value="user_pos">📍 My Current Location (Blue Dot)</option>';
    this.navGoalSelect.innerHTML = '<option value="">Choose destination...</option>';

    pois.forEach((poi) => {
      const opt1 = document.createElement('option');
      opt1.value = poi.id;
      opt1.textContent = `${poi.name} [${poi.category}]`;
      this.navStartSelect.appendChild(opt1);

      const opt2 = document.createElement('option');
      opt2.value = poi.id;
      opt2.textContent = `${poi.name} [${poi.category}]`;
      this.navGoalSelect.appendChild(opt2);
    });
  }

  // --- Place Details Sheet (Google Maps Style) ---
  showPlaceSheet(poi, onDirections, onSetStart, onFocus) {
    this.activePOI = poi;
    this.placeCategory.textContent = (poi.category || 'Location').replace('_', ' ').toUpperCase();
    this.placeTitle.textContent = poi.name;
    this.placeDescription.textContent = poi.description || 'Indoor point of interest.';
    this.placeCoords.textContent = `(${poi.position.x.toFixed(1)}, ${poi.position.z.toFixed(1)})`;
    this.placeFloor.textContent = poi.floor === 1 ? 'L2' : 'L1';

    // Tags
    this.placeTags.innerHTML = '';
    if (poi.tags && poi.tags.length > 0) {
      poi.tags.forEach((tag) => {
        const span = document.createElement('span');
        span.className = 'place-tag';
        span.textContent = `#${tag}`;
        this.placeTags.appendChild(span);
      });
    }

    // Directions button: opens directions panel with this as destination
    this.btnPlaceDirections.onclick = () => {
      this.hidePlaceSheet();
      this.navGoalSelect.value = poi.id;
      this.directionsPanel.classList.remove('hidden');
      if (onDirections) onDirections(poi);
    };

    this.btnPlaceSetStart.onclick = () => {
      this.navStartSelect.value = poi.id;
      this.showToast(`Set '${poi.name}' as starting point.`, 'success');
      if (onSetStart) onSetStart(poi);
    };

    this.btnPlaceFocus.onclick = () => {
      if (onFocus) onFocus(poi);
    };

    this.gmapsPlaceSheet.classList.remove('hidden');
  }

  hidePlaceSheet() {
    this.gmapsPlaceSheet?.classList.add('hidden');
    this.activePOI = null;
  }

  // --- Search Autocomplete Results ---
  showSearchResults(results, onSelect) {
    this.searchResultsDropdown.innerHTML = '';
    this.searchResultsDropdown.classList.remove('hidden');

    if (!results || results.length === 0) {
      this.searchResultsDropdown.innerHTML = `
        <div class="search-empty-state">No matching indoor locations found.</div>
      `;
      return;
    }

    results.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'search-result-item';
      const distStr = item.distance !== undefined ? ` • ${item.distance.toFixed(1)}m away` : '';
      const matchedFieldStr = item.matched_field ? `matched ${item.matched_field}` : '';

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
    this.searchResultsDropdown?.classList.add('hidden');
  }

  // --- Route & Natural Directions Display ---
  showRouteSummary(navData) {
    // Show summary in directions panel
    this.directionsStepContainer?.classList.remove('hidden');
    this.routeTimeVal.textContent = `${Math.round(navData.estimated_walking_time_seconds)} s`;
    this.routeDistVal.textContent = `(${navData.total_distance_meters.toFixed(1)} m)`;
    this.routeLatencyBadge.textContent = `A* ${navData.execution_time_ms.toFixed(0)}ms`;

    // Dynamic Hazard Reroute Alert
    if (navData.rerouted_due_to_obstacles) {
      const avoidedStr =
        navData.avoided_obstacles && navData.avoided_obstacles.length > 0
          ? ` (${navData.avoided_obstacles.join(', ')})`
          : '';
      this.routeRerouteAlert.innerHTML = `<span>⚠️ Rerouted around floor spill hazard${avoidedStr}!</span>`;
      this.routeRerouteAlert.classList.remove('hidden');
    } else {
      this.routeRerouteAlert.classList.add('hidden');
    }

    // Populate Natural Directions Step List
    this.directionsList.innerHTML = '';
    const directions = navData.directions || [];
    directions.forEach((d) => {
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

    // Also Show Google Maps Bottom Trip Bar
    this.showTripBar(
      navData.estimated_walking_time_seconds,
      navData.total_distance_meters,
      directions.length
    );
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

  // --- Tooltips & Toasts ---
  showHoverTooltip(poi, clientX, clientY) {
    if (!poi) {
      this.poiHoverTooltip?.classList.add('hidden');
      return;
    }
    this.tooltipTitle.textContent = poi.name;
    this.tooltipCategory.textContent = (poi.category || '').toUpperCase();
    this.poiHoverTooltip.style.left = `${clientX + 14}px`;
    this.poiHoverTooltip.style.top = `${clientY + 14}px`;
    this.poiHoverTooltip.classList.remove('hidden');
  }

  showToast(message, type = 'info') {
    if (!this.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    this.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }
}
