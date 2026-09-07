/**
 * FARECAST API Service Layer
 * 
 * Interacts with the FastAPI backend.
 * Uses VITE_API_BASE_URL if configured, otherwise falls back to window origin or dev proxy.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      let errDetails = null;
      try {
        errDetails = await response.json();
      } catch {
        // Response body might not be JSON
      }
      const message = errDetails?.detail || `API error (${response.status}): ${response.statusText}`;
      throw new ApiError(message, response.status, errDetails);
    }

    return await response.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err.message || 'Network request failed', 0);
  }
}

export const api = {
  // System Health
  getHealth: () => request('/health'),

  // Dashboard Overview
  getDashboardSummary: () => request('/api/dashboard/summary'),

  // Routes & Airlines
  getRoutes: () => request('/api/routes'),
  getAirlines: () => request('/api/airlines'),

  // Fares
  getFares: (params = {}) => {
    const query = new URLSearchParams();
    if (params.origin) query.append('origin', params.origin);
    if (params.destination) query.append('destination', params.destination);
    if (params.airline) query.append('airline', params.airline);
    if (params.cabin_class) query.append('cabin_class', params.cabin_class);
    if (params.travel_date_from) query.append('travel_date_from', params.travel_date_from);
    if (params.travel_date_to) query.append('travel_date_to', params.travel_date_to);
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);

    const qs = query.toString();
    return request(`/api/fares${qs ? `?${qs}` : ''}`);
  },

  getLeadTimeElasticity: (params = {}) => {
    const query = new URLSearchParams();
    if (params.origin) query.append('origin', params.origin);
    if (params.destination) query.append('destination', params.destination);
    const qs = query.toString();
    return request(`/api/fares/elasticity${qs ? `?${qs}` : ''}`);
  },

  getSectorMatrix: () => request('/api/fares/sector-matrix'),

  // Prototype Index
  getIndex: (params = {}) => {
    const query = new URLSearchParams();
    if (params.period) query.append('period', params.period);
    if (params.period_type) query.append('period_type', params.period_type);
    if (params.limit) query.append('limit', params.limit || 100);
    if (params.offset) query.append('offset', params.offset || 0);

    const qs = query.toString();
    return request(`/api/index${qs ? `?${qs}` : ''}`);
  },

  getRouteIndex: (origin, destination) => {
    return request(`/api/index/${encodeURIComponent(origin)}/${encodeURIComponent(destination)}`);
  },

  // Fare Forecast / ML Prediction
  getPrediction: (params) => {
    const query = new URLSearchParams();
    query.append('origin', params.origin);
    query.append('destination', params.destination);
    if (params.airline) query.append('airline', params.airline);
    if (params.cabin_class) query.append('cabin_class', params.cabin_class);
    if (params.departure_time) query.append('departure_time', params.departure_time);
    if (params.arrival_time) query.append('arrival_time', params.arrival_time);
    if (params.stops !== undefined) query.append('stops', params.stops);
    if (params.duration_minutes) query.append('duration_minutes', params.duration_minutes);
    if (params.days_left) query.append('days_left', params.days_left);

    return request(`/api/prediction?${query.toString()}`);
  },

  // Anomalies / Market Signals
  getAnomalies: (params = {}) => {
    const query = new URLSearchParams();
    if (params.route) query.append('route', params.route);
    if (params.severity) query.append('severity', params.severity);
    if (params.method) query.append('method', params.method);
    if (params.limit) query.append('limit', params.limit || 50);
    if (params.offset) query.append('offset', params.offset || 0);

    const qs = query.toString();
    return request(`/api/anomalies${qs ? `?${qs}` : ''}`);
  },

  // DGCA Statistics
  getDgca: (params = {}) => {
    const query = new URLSearchParams();
    if (params.period) query.append('period', params.period);
    if (params.airline) query.append('airline', params.airline);
    if (params.origin) query.append('origin', params.origin);
    if (params.destination) query.append('destination', params.destination);
    if (params.limit) query.append('limit', params.limit || 50);
    if (params.offset) query.append('offset', params.offset || 0);

    const qs = query.toString();
    return request(`/api/dgca${qs ? `?${qs}` : ''}`);
  },

  getDgcaSummary: () => request('/api/dgca/summary'),

  // MoSPI / CPI Reference Data
  getCpi: () => request('/api/cpi'),

  // Live Status & Search
  getLiveStatus: () => request('/api/live/status'),

  searchLiveFares: (params) => {
    const query = new URLSearchParams();
    query.append('origin', params.origin);
    query.append('destination', params.destination);
    query.append('departure_date', params.departure_date);
    if (params.adults) query.append('adults', params.adults);
    if (params.travel_class) query.append('travel_class', params.travel_class);
    if (params.max_results) query.append('max_results', params.max_results);

    return request(`/api/live/search?${query.toString()}`);
  },

  // NSO & RBI Regulatory Consumption API
  getNsoApix: (params = {}) => {
    const query = new URLSearchParams();
    if (params.frequency) query.append('frequency', params.frequency);
    if (params.sub_index) query.append('sub_index', params.sub_index);
    if (params.route) query.append('route', params.route);
    if (params.period) query.append('period', params.period);
    const qs = query.toString();
    return request(`/api/v1/nso/apix${qs ? `?${qs}` : ''}`);
  },

  getNsoExportUrl: (frequency = 'monthly') => {
    return `${API_BASE_URL}/api/v1/nso/apix/export?frequency=${encodeURIComponent(frequency)}`;
  },

  getRbiMacroFeed: () => request('/api/v1/rbi/macro-feed'),

  getBacktestResults: (mode = 'empirical') => request(`/api/v1/analytics/backtest-results?mode=${encodeURIComponent(mode)}`),

  // Scraper compliance audit
  getScraperCompliance: () => request('/api/scrapers/compliance'),
};

