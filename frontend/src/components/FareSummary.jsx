import React from 'react';
import { formatINR, formatNumber } from '../utils/formatters';

export default function FareSummary({ faresData, summaryMeta }) {
  // Compute from faresData if available
  const records = faresData?.data || [];
  
  let avgFare = null;
  let minFare = null;
  let maxFare = null;
  let totalObservations = summaryMeta?.total_fare_observations || 0;

  if (records.length > 0) {
    const fares = records.map((r) => r.fare).filter((f) => f !== null && !isNaN(f));
    if (fares.length > 0) {
      avgFare = fares.reduce((a, b) => a + b, 0) / fares.length;
      minFare = Math.min(...fares);
      maxFare = Math.max(...fares);
      totalObservations = faresData.meta?.total || records.length;
    }
  }

  return (
    <section className="summary-grid" aria-label="Fare Observations Summary">
      <div className="summary-card highlight">
        <div className="summary-label">Average Observed Fare</div>
        <div className="summary-value mono-num" id="stat-avg-fare">
          {formatINR(avgFare)}
        </div>
        <div className="summary-delta">
          Across {formatNumber(totalObservations)} filtered records
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-label">Minimum Observed Fare</div>
        <div className="summary-value mono-num" id="stat-min-fare">
          {formatINR(minFare)}
        </div>
        <div className="summary-delta">
          Lowest fare observed
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-label">Maximum Observed Fare</div>
        <div className="summary-value mono-num" id="stat-max-fare">
          {formatINR(maxFare)}
        </div>
        <div className="summary-delta">
          Peak observed fare
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-label">Total Observations</div>
        <div className="summary-value mono-num" id="stat-obs-count">
          {formatNumber(totalObservations)}
        </div>
        <div className="summary-delta">
          Verified historical records
        </div>
      </div>
    </section>
  );
}
