/**
 * NammaSpace 3D - API Client
 * Seamlessly interfaces with FastAPI backend for venues, POIs, fuzzy search, and A* navigation.
 */

class ApiClient {
  constructor() {
    // Auto-detect base URL: if running from backend server, origin is '', else localhost:8000
    const origin = window.location.origin;
    if (origin.includes('8000') || origin.includes('vercel.app')) {
      this.baseUrl = '';
    } else {
      this.baseUrl = 'http://localhost:8000';
    }
    this.lastLatencyMs = 0;
  }

  async _fetch(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const t0 = performance.now();
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        },
        ...options
      });

      const latency = Math.round(performance.now() - t0);
      const serverLatency = response.headers.get('X-Process-Time-Ms');
      this.lastLatencyMs = serverLatency ? parseFloat(serverLatency) : latency;

      if (!response.ok) {
        let errData;
        try {
          errData = await response.json();
        } catch {
          errData = { message: response.statusText };
        }
        throw new Error(errData.message || `Request failed with HTTP ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      this.lastLatencyMs = Math.round(performance.now() - t0);
      throw err;
    }
  }

  async checkHealth() {
    return await this._fetch('/health');
  }

  async listVenues() {
    return await this._fetch('/venues');
  }

  async getVenue(venueId) {
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}`);
  }

  async getPOIs(venueId, options = {}) {
    const params = new URLSearchParams();
    if (options.category) params.append('category', options.category);
    if (options.floor !== undefined) params.append('floor', options.floor);
    if (options.x !== undefined && options.z !== undefined && options.radius !== undefined) {
      params.append('x', options.x);
      params.append('y', options.y || 0.0);
      params.append('z', options.z);
      params.append('radius', options.radius);
    }
    const queryStr = params.toString() ? `?${params.toString()}` : '';
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}/pois${queryStr}`);
  }

  async searchPOIs(venueId, query, userPos = null) {
    const params = new URLSearchParams({ q: query });
    if (userPos && userPos.x !== undefined && userPos.z !== undefined) {
      params.append('user_x', userPos.x);
      params.append('user_z', userPos.z);
    }
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}/search?${params.toString()}`);
  }

  async navigate(venueId, start, goal, smoothPath = true) {
    const payload = {
      start,
      goal,
      smooth_path: smoothPath
    };
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}/navigate`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  async listObstacles(venueId) {
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}/obstacles`);
  }

  async createObstacle(venueId, obstacle) {
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}/obstacles`, {
      method: 'POST',
      body: JSON.stringify(obstacle)
    });
  }

  async deleteObstacle(venueId, obstacleId) {
    return await this._fetch(
      `/venues/${encodeURIComponent(venueId)}/obstacles/${encodeURIComponent(obstacleId)}`,
      { method: 'DELETE' }
    );
  }

  async clearObstacles(venueId) {
    return await this._fetch(`/venues/${encodeURIComponent(venueId)}/obstacles/clear`, {
      method: 'POST'
    });
  }

  getModelUrl(venueId, modelFile) {
    return `${this.baseUrl}/static/venues/${venueId}/${modelFile}`;
  }

  getNavmeshDebugUrl(venueId) {
    return `${this.baseUrl}/static/venues/${venueId}/debug_map.png`;
  }
}

export const api = new ApiClient();

