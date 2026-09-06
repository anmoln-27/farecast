import React from 'react';
import EmptyState from './EmptyState';
import { formatINR, formatDate, formatPercent } from '../utils/formatters';

export default function MarketSignals({ anomalies = [], loading = false }) {
  if (loading) {
    return (
      <div className="panel" id="section-market-signals">
        <div className="panel-header">
          <div className="panel-title-group">
            <span className="panel-title">MARKET SIGNALS</span>
            <span className="panel-subtitle">Statistical deviations and fare anomalies detected via IQR &amp; Isolation Forest</span>
          </div>
        </div>
        <div className="panel-body">
          <div className="loading-skeleton">Loading anomaly observations...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel" id="section-market-signals">
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-title">MARKET SIGNALS</span>
          <span className="panel-subtitle">Statistical fare anomalies detected via IQR and Isolation Forest methods</span>
        </div>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {anomalies.length} Signal{anomalies.length === 1 ? '' : 's'} Detected
        </span>
      </div>

      <div className="panel-body" style={{ padding: 0 }}>
        {anomalies.length === 0 ? (
          <EmptyState
            title="No market signals detected"
            message="All observations within the selected scope fall within normal statistical thresholds."
          />
        ) : (
          <div className="data-table-wrapper">
            <table className="data-table" aria-label="Detected Fare Anomalies">
              <thead>
                <tr>
                  <th>Route</th>
                  <th>Airline</th>
                  <th>Travel Date</th>
                  <th>Days Out</th>
                  <th>Observed Fare</th>
                  <th>Expected Fare</th>
                  <th>Deviation</th>
                  <th>Severity</th>
                  <th>Method</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.map((item) => {
                  const sev = (item.severity || 'normal').toLowerCase();
                  let badgeClass = 'badge-normal';
                  if (sev === 'high') badgeClass = 'badge-high';
                  else if (sev === 'watch') badgeClass = 'badge-watch';

                  return (
                    <tr key={item.id}>
                      <td style={{ fontWeight: 600 }}>{item.route}</td>
                      <td>{item.airline || '—'}</td>
                      <td>{formatDate(item.travel_date)}</td>
                      <td className="mono-num">{item.days_left !== null ? `${item.days_left}d` : '—'}</td>
                      <td className="mono-num" style={{ fontWeight: 600 }}>
                        {formatINR(item.observed_fare)}
                      </td>
                      <td className="mono-num" style={{ color: 'var(--text-muted)' }}>
                        {formatINR(item.expected_fare)}
                      </td>
                      <td
                        className="mono-num"
                        style={{
                          fontWeight: 500,
                          color: item.deviation_percentage && item.deviation_percentage > 0 ? '#991B1B' : '#065F46',
                        }}
                      >
                        {formatPercent(item.deviation_percentage)}
                      </td>
                      <td>
                        <span className={`badge ${badgeClass}`}>
                          {item.severity || 'NORMAL'}
                        </span>
                      </td>
                      <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {item.method || 'Statistical'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
