import React from 'react';
import { formatINR, formatNumber } from '../utils/formatters';

export default function FareSummary({ faresData, summaryMeta }) {
  // ── Primary: use pre-aggregated stats from the backend dashboard summary ──
  // These cover the FULL dataset (not a paginated 100-record subset).
  const totalObservations = summaryMeta?.total_fare_observations ?? (faresData?.meta?.total ?? 0);

  // Backend now returns avg_fare, min_fare, max_fare computed via SQL over all rows.
  // Fall back to computing from the local faresData page only if summaryMeta aggregates are absent.
  let avgFare = (summaryMeta?.avg_fare != null) ? summaryMeta.avg_fare : null;
  let minFare = (summaryMeta?.min_fare != null) ? summaryMeta.min_fare : null;
  let maxFare = (summaryMeta?.max_fare != null) ? summaryMeta.max_fare : null;

  if (avgFare === null || minFare === null || maxFare === null) {
    // Fallback: compute from paginated records (partial dataset)
    const records = faresData?.data || [];
    if (records.length > 0) {
      const fares = records.map((r) => Number(r.fare)).filter((f) => !isNaN(f) && f > 0);
      if (fares.length > 0) {
        if (avgFare === null) avgFare = fares.reduce((a, b) => a + b, 0) / fares.length;
        if (minFare === null) minFare = Math.min(...fares);
        if (maxFare === null) maxFare = Math.max(...fares);
      }
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
          Across {formatNumber(totalObservations)} historical records
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
