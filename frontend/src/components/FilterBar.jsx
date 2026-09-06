import React from 'react';

const DEFAULT_CITIES = [
  { code: 'DEL', name: 'Delhi (DEL)' },
  { code: 'BOM', name: 'Mumbai (BOM)' },
  { code: 'BLR', name: 'Bangalore (BLR)' },
  { code: 'HYD', name: 'Hyderabad (HYD)' },
  { code: 'CCU', name: 'Kolkata (CCU)' },
  { code: 'MAA', name: 'Chennai (MAA)' },
  { code: 'PNQ', name: 'Pune (PNQ)' },
  { code: 'GOI', name: 'Goa (GOI)' },
];

export default function FilterBar({
  filters,
  onChange,
  onApply,
  onReset,
  routes = [],
  airlines = [],
  loading = false,
}) {
  // Derive origins and destinations from available DB routes, or fallback to DEFAULT_CITIES
  const origins = routes.length > 0
    ? Array.from(new Set(routes.map((r) => r.origin))).sort()
    : DEFAULT_CITIES.map((c) => c.code);

  const destinations = routes.length > 0
    ? Array.from(new Set(routes.map((r) => r.destination))).sort()
    : DEFAULT_CITIES.map((c) => c.code);

  return (
    <div className="filter-bar-panel">
      <div className="filter-grid">
        <div className="filter-item">
          <label className="filter-label" htmlFor="filter-origin">Origin</label>
          <select
            id="filter-origin"
            className="filter-select"
            value={filters.origin || ''}
            onChange={(e) => onChange('origin', e.target.value)}
          >
            <option value="">All Origins</option>
            {origins.map((code) => {
              const cityMatch = DEFAULT_CITIES.find((c) => c.code === code);
              return (
                <option key={code} value={code}>
                  {cityMatch ? cityMatch.name : code}
                </option>
              );
            })}
          </select>
        </div>

        <div className="filter-item">
          <label className="filter-label" htmlFor="filter-destination">Destination</label>
          <select
            id="filter-destination"
            className="filter-select"
            value={filters.destination || ''}
            onChange={(e) => onChange('destination', e.target.value)}
          >
            <option value="">All Destinations</option>
            {destinations.map((code) => {
              const cityMatch = DEFAULT_CITIES.find((c) => c.code === code);
              return (
                <option key={code} value={code}>
                  {cityMatch ? cityMatch.name : code}
                </option>
              );
            })}
          </select>
        </div>

        <div className="filter-item">
          <label className="filter-label" htmlFor="filter-date">Travel Date</label>
          <input
            id="filter-date"
            type="date"
            className="filter-input"
            value={filters.travel_date || ''}
            onChange={(e) => onChange('travel_date', e.target.value)}
          />
        </div>

        <div className="filter-item">
          <label className="filter-label" htmlFor="filter-airline">Airline</label>
          <select
            id="filter-airline"
            className="filter-select"
            value={filters.airline || ''}
            onChange={(e) => onChange('airline', e.target.value)}
          >
            <option value="">All Airlines</option>
            {airlines.map((a) => (
              <option key={a.code} value={a.code}>
                {a.name} ({a.code})
              </option>
            ))}
          </select>
        </div>

        <div className="filter-item">
          <label className="filter-label" htmlFor="filter-cabin">Cabin Class</label>
          <select
            id="filter-cabin"
            className="filter-select"
            value={filters.cabin_class || ''}
            onChange={(e) => onChange('cabin_class', e.target.value)}
          >
            <option value="">All Classes</option>
            <option value="Economy">Economy</option>
            <option value="Business">Business</option>
          </select>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignSelf: 'flex-end' }}>
          <button
            type="button"
            className="btn-primary"
            onClick={onApply}
            disabled={loading}
            id="btn-apply-filter"
          >
            {loading ? 'Filtering...' : 'Apply Filters'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={onReset}
            disabled={loading}
            id="btn-reset-filter"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
