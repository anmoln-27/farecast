import React from 'react';
import { formatPercent } from '../utils/formatters';

export default function IndexSection({ indexData, selectedRoute, selectedDate }) {
  const records = indexData?.data || [];

  // Match specific route if filtered, otherwise find national AGGREGATE
  let activeRecord = null;

  const routeRecords = selectedRoute
    ? records.filter((r) => r.route === selectedRoute)
    : records.filter((r) => r.route === 'AGGREGATE');

  let pool = routeRecords;
  if (pool.length === 0) {
    // If route-specific index is missing, fallback to AGGREGATE
    pool = records.filter((r) => r.route === 'AGGREGATE');
  }
  if (pool.length === 0) {
    pool = records;
  }

  if (selectedDate && pool.length > 0) {
    // Check if exact date/period matches (e.g., 2022-04-01 or 2022-04)
    const exactMatch = pool.find(
      (r) => r.period === selectedDate || selectedDate.startsWith(r.period) || (r.period && r.period.startsWith(selectedDate.slice(0, 7)))
    );
    if (exactMatch) {
      activeRecord = exactMatch;
    } else {
      activeRecord = pool[0];
    }
  } else {
    activeRecord = pool[0] || null;
  }

  const indexValue = activeRecord?.index_value;
  const period = activeRecord?.period || 'Latest Period';
  const displayRoute = selectedRoute || activeRecord?.route || 'National Aggregate';

  // Calculate change vs baseline (base is 100)
  const changeVsBaseline = indexValue != null ? indexValue - 100 : null;

  return (
    <section className="index-banner" aria-label="Airfare Price Index">
      <div className="index-details">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
          <span className="prototype-tag">AIRFARE PRICE INDEX</span>
        </div>
        <h2 className="index-title serif-heading">
          {selectedRoute ? `Route Price Index: ${selectedRoute}` : `Airfare Price Index: ${displayRoute}`}
        </h2>
        <p className="index-disclaimer">
          Experimental airfare benchmark with Base Period = 100.
          <strong> Not an official Government of India statistical publication.</strong>
        </p>
      </div>

      <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
        <div className="index-metric-box">
          <div>
            <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
              Period: {period}
            </div>
            <div className="index-large-val mono-num">
              {indexValue !== null && indexValue !== undefined ? indexValue.toFixed(1) : '—'}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: changeVsBaseline === null ? 'var(--text-secondary)' : changeVsBaseline > 0 ? '#991B1B' : '#065F46',
              }}
              className="mono-num"
            >
              {changeVsBaseline !== null ? `${changeVsBaseline > 0 ? '↑' : '↓'} ${formatPercent(changeVsBaseline)}` : 'Index unavailable'}
            </div>
            <div className="index-baseline-ref">vs. Baseline</div>
          </div>
        </div>
      </div>
    </section>
  );
}
