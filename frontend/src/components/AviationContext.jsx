import React from 'react';
import EmptyState from './EmptyState';
import { formatNumber, formatPercent } from '../utils/formatters';

export default function AviationContext({ dgcaRecords = [], dgcaSummary, cpiRecords = [] }) {
  return (
    <div className="dashboard-grid full-width" id="section-aviation-context">
      {/* DGCA Aviation Context */}
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title-group">
            <span className="panel-title">DGCA AVIATION CONTEXT</span>
            <span className="panel-subtitle">Directorate General of Civil Aviation domestic capacity &amp; traffic statistics</span>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Official Registry</span>
        </div>
        <div className="panel-body" style={{ padding: dgcaRecords.length > 0 ? 0 : '20px' }}>
          {dgcaRecords.length === 0 ? (
            <EmptyState
              title="No DGCA records loaded"
              message="DGCA domestic traffic &amp; capacity statistics provide macro route context (seats, passengers, load factor). Ingest data via load_dgca script."
            />
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table" aria-label="DGCA Aviation Context Statistics">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Airline</th>
                    <th>Route</th>
                    <th>Passengers</th>
                    <th>Flights</th>
                    <th>Seats</th>
                    <th>Load Factor</th>
                  </tr>
                </thead>
                <tbody>
                  {dgcaRecords.slice(0, 8).map((rec) => (
                    <tr key={rec.id}>
                      <td className="mono-num">{rec.period}</td>
                      <td>{rec.airline || 'Domestic Aggregate'}</td>
                      <td>{rec.origin && rec.destination ? `${rec.origin}-${rec.destination}` : 'All Routes'}</td>
                      <td className="mono-num">{formatNumber(rec.passengers)}</td>
                      <td className="mono-num">{formatNumber(rec.flights_operated)}</td>
                      <td className="mono-num">{formatNumber(rec.seats_offered)}</td>
                      <td className="mono-num">
                        {rec.load_factor ? `${(rec.load_factor * (rec.load_factor > 1 ? 1 : 100)).toFixed(1)}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div
            style={{
              padding: '12px 16px',
              borderTop: '1px solid var(--border-color)',
              background: '#FBFBFB',
              fontSize: '11px',
              color: 'var(--text-secondary)',
            }}
          >
            <strong>Note:</strong> Official DGCA aviation statistics represent operational traffic and seat capacity, <em>not</em> individual ticket-price observations.
          </div>
        </div>
      </div>

      {/* MoSPI / CPI Reference */}
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title-group">
            <span className="panel-title">MOSPI / CPI REFERENCE</span>
            <span className="panel-subtitle">Ministry of Statistics &amp; Programme Implementation reference benchmarks</span>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Base Year: 2012=100</span>
        </div>
        <div className="panel-body" style={{ padding: cpiRecords.length > 0 ? 0 : '20px' }}>
          {cpiRecords.length === 0 ? (
            <EmptyState
              title="No CPI reference records"
              message="MoSPI Transport &amp; Communication benchmark indexes are loaded as macroeconomic baseline context."
            />
          ) : (
            <div className="data-table-wrapper">
              <table className="data-table" aria-label="MoSPI CPI Reference Data">
                <thead>
                  <tr>
                    <th>Indicator</th>
                    <th>Period</th>
                    <th>Base Year</th>
                    <th>Index Value</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {cpiRecords.map((rec) => (
                    <tr key={rec.id}>
                      <td style={{ fontWeight: 500 }}>{rec.indicator}</td>
                      <td className="mono-num">{rec.period}</td>
                      <td className="mono-num">{rec.base_year || '2012'}</td>
                      <td className="mono-num" style={{ fontWeight: 700 }}>
                        {rec.value !== null ? rec.value.toFixed(1) : '—'}
                      </td>
                      <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {rec.source || 'MoSPI'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div
            style={{
              padding: '12px 16px',
              borderTop: '1px solid var(--border-color)',
              background: '#FBFBFB',
              fontSize: '11px',
              color: 'var(--text-secondary)',
            }}
          >
            <strong>Disclaimer:</strong> MoSPI CPI data is macroeconomic reference context (Transport &amp; Communication group) and is <em>not</em> presented as flight-level CPI observations.
          </div>
        </div>
      </div>
    </div>
  );
}
