import React from 'react';
import { formatPercent } from '../utils/formatters';

export default function IndexSection({ indexData, selectedRoute }) {
  const records = indexData?.data || [];

  // Match specific route if filtered, otherwise find national AGGREGATE
  let activeRecord = null;
  if (selectedRoute) {
    activeRecord = records.find((r) => r.route === selectedRoute) || records[0];
  } else {
    activeRecord = records.find((r) => r.route === 'AGGREGATE') || records[0];
  }

  const indexValue = activeRecord?.index_value;
  const baselineFare = activeRecord?.baseline_fare;
  const avgFare = activeRecord?.avg_fare;
  const period = activeRecord?.period || 'Latest Period';
  const baselinePeriod = activeRecord?.baseline_period || '2022-02';
  const displayRoute = activeRecord?.route || selectedRoute || 'National Aggregate';

  // Calculate change vs baseline (base is 100)
  const changeVsBaseline = indexValue != null ? indexValue - 100 : null;

  return (
    <section className="index-banner" aria-label="Prototype Airfare Price Index">
      <div className="index-details">
        <span className="prototype-tag">PROTOTYPE INDEX</span>
        <h2 className="index-title serif-heading">
          {selectedRoute ? `Route Price Index: ${selectedRoute}` : `National Airfare Price Index (${displayRoute})`}
        </h2>
        <p className="index-disclaimer">
          Experimental benchmark computed from historical fare observations using equal-weight / DGCA traffic methodology (Base = 100.0, Baseline: {baselinePeriod} @ {baselineFare ? `₹${Math.round(baselineFare)}` : 'Ref'}).
          <strong> NOT an official Government of India statistical publication.</strong>
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
              {changeVsBaseline !== null ? `${changeVsBaseline > 0 ? '↑' : '↓'} ${formatPercent(changeVsBaseline)}` : 'Index unavailable — insufficient observations'}
            </div>
            <div className="index-baseline-ref">vs. Baseline</div>
          </div>
        </div>
      </div>
    </section>
  );
}
