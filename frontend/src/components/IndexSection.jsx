import React from 'react';
import { formatPercent } from '../utils/formatters';

export default function IndexSection({ indexData, selectedRoute, selectedDate }) {
  const records = indexData?.data || [];

  // Match specific route if filtered, otherwise find national AGGREGATE
  let activeRecord = null;
  let isNearestPeriod = false;
  let isFallbackAggregate = false;

  const routeRecords = selectedRoute
    ? records.filter((r) => r.route === selectedRoute)
    : records.filter((r) => r.route === 'AGGREGATE');

  let pool = routeRecords;
  if (pool.length === 0) {
    // If route-specific index is missing, fallback to AGGREGATE
    pool = records.filter((r) => r.route === 'AGGREGATE');
    isFallbackAggregate = true;
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
      isNearestPeriod = true;
    }
  } else {
    activeRecord = pool[0] || null;
  }

  const indexValue = activeRecord?.index_value;
  const baselineFare = activeRecord?.baseline_fare;
  const period = activeRecord?.period || 'Latest Period';
  const baselinePeriod = activeRecord?.baseline_period || '2022-02';
  const displayRoute = activeRecord?.route || selectedRoute || 'National Aggregate';

  // Calculate change vs baseline (base is 100)
  const changeVsBaseline = indexValue != null ? indexValue - 100 : null;

  return (
    <section className="index-banner" aria-label="Airfare Price Index">
      <div className="index-details">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
          <span className="prototype-tag">AIRFARE PRICE INDEX</span>
          {isNearestPeriod && (
            <span style={{ fontSize: '11px', background: '#FEF3C7', color: '#92400E', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
              Nearest Available Period
            </span>
          )}
          {isFallbackAggregate && (
            <span style={{ fontSize: '11px', background: '#E0E7FF', color: '#3730A3', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
              National Aggregate Baseline
            </span>
          )}
        </div>
        <h2 className="index-title serif-heading">
          {selectedRoute && !isFallbackAggregate ? `Route Price Index: ${selectedRoute}` : `National Airfare Price Index (${displayRoute})`}
        </h2>
        <p className="index-disclaimer">
          {isFallbackAggregate
            ? "Route-specific index unavailable. Showing documented national aggregate index as baseline. "
            : isNearestPeriod
            ? "Using available observations — no records for the exact selected date. "
            : ""}
          Experimental airfare benchmark with Base Period = 100 (Baseline: {baselinePeriod} @ {baselineFare ? `₹${Math.round(baselineFare)}` : 'Ref'}).
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
