import React from 'react';
import { formatPercent } from '../utils/formatters';

export default function IndexSection({ indexData, selectedRoute }) {
  // If we have index records
  const records = indexData?.data || [];
  const latestRecord = records.length > 0 ? records[0] : null;
  const indexValue = latestRecord?.index_value;
  const baselineFare = latestRecord?.baseline_fare;
  const avgFare = latestRecord?.avg_fare;
  const period = latestRecord?.period || 'Latest Period';

  // Calculate change vs baseline (base is 100)
  const changeVsBaseline = indexValue ? indexValue - 100 : null;

  return (
    <section className="index-banner" aria-label="Prototype Airfare Price Index">
      <div className="index-details">
        <span className="prototype-tag">PROTOTYPE INDEX</span>
        <h2 className="index-title serif-heading">
          {selectedRoute ? `Route Price Index: ${selectedRoute}` : 'National Airfare Price Index (Prototype)'}
        </h2>
        <p className="index-disclaimer">
          Experimental benchmark computed from historical fare observations using equal-weight methodology (Base Period = 100).
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
              {indexValue !== null && indexValue !== undefined ? indexValue.toFixed(1) : '100.0'}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: changeVsBaseline === null ? 'var(--text-secondary)' : changeVsBaseline > 0 ? '#991B1B' : '#065F46',
              }}
              className="mono-num"
            >
              {changeVsBaseline !== null ? formatPercent(changeVsBaseline) : 'Base (100.0)'}
            </div>
            <div className="index-baseline-ref">vs. Baseline</div>
          </div>
        </div>
      </div>
    </section>
  );
}
