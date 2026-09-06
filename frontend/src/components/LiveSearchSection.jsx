import React, { useState } from 'react';
import { api } from '../services/api';
import EmptyState from './EmptyState';
import { formatINR } from '../utils/formatters';

export default function LiveSearchSection({ liveStatus }) {
  const [params, setParams] = useState({
    origin: 'DEL',
    destination: 'BOM',
    departure_date: new Date(Date.now() + 86400000 * 7).toISOString().split('T')[0], // 7 days ahead
    travel_class: 'ECONOMY',
    adults: 1,
  });

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!params.origin || !params.destination || !params.departure_date) return;
    if (params.origin === params.destination) {
      setError('Origin and destination cannot be identical.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.searchLiveFares(params);
      setResults(res);
    } catch (err) {
      setError(err.message || 'Live flight search query failed.');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const mode = results?.data_mode || (liveStatus?.demo_mode ? 'DEMO' : 'HISTORICAL');
  const isLive = mode === 'LIVE';

  return (
    <div className="panel full-width" id="section-live-search">
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-title">LIVE AIRFARE SEARCH (AMADEUS API)</span>
          <span className="panel-subtitle">Global Distribution System live query with automated DEMO historical fallback</span>
        </div>
        <div className={`status-indicator ${isLive ? 'live' : 'demo'}`}>
          <span className="status-dot"></span>
          <span>{isLive ? 'LIVE AMADEUS' : 'DEMO MODE FALLBACK'}</span>
        </div>
      </div>

      <div className="panel-body">
        <form onSubmit={handleSearch} style={{ marginBottom: '20px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '12px',
              alignItems: 'flex-end',
            }}
          >
            <div className="filter-item">
              <label className="filter-label" htmlFor="live-origin">Origin (IATA)</label>
              <select
                id="live-origin"
                className="filter-select"
                value={params.origin}
                onChange={(e) => setParams({ ...params, origin: e.target.value })}
              >
                <option value="DEL">DEL — New Delhi</option>
                <option value="BOM">BOM — Mumbai</option>
                <option value="BLR">BLR — Bangalore</option>
                <option value="HYD">HYD — Hyderabad</option>
                <option value="CCU">CCU — Kolkata</option>
                <option value="MAA">MAA — Chennai</option>
              </select>
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="live-dest">Destination (IATA)</label>
              <select
                id="live-dest"
                className="filter-select"
                value={params.destination}
                onChange={(e) => setParams({ ...params, destination: e.target.value })}
              >
                <option value="BOM">BOM — Mumbai</option>
                <option value="DEL">DEL — New Delhi</option>
                <option value="BLR">BLR — Bangalore</option>
                <option value="HYD">HYD — Hyderabad</option>
                <option value="CCU">CCU — Kolkata</option>
                <option value="MAA">MAA — Chennai</option>
              </select>
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="live-date">Departure Date</label>
              <input
                id="live-date"
                type="date"
                className="filter-input"
                value={params.departure_date}
                onChange={(e) => setParams({ ...params, departure_date: e.target.value })}
              />
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="live-class">Travel Class</label>
              <select
                id="live-class"
                className="filter-select"
                value={params.travel_class}
                onChange={(e) => setParams({ ...params, travel_class: e.target.value })}
              >
                <option value="ECONOMY">Economy</option>
                <option value="BUSINESS">Business</option>
              </select>
            </div>

            <button
              type="submit"
              className="btn-primary"
              disabled={loading || params.origin === params.destination}
              id="btn-execute-live-search"
            >
              {loading ? 'Searching...' : 'Search Fares'}
            </button>
          </div>
        </form>

        {error && (
          <div
            style={{
              padding: '12px 16px',
              background: '#FEF2F2',
              color: '#991B1B',
              border: '1px solid #FECACA',
              borderRadius: 'var(--radius-sm)',
              fontSize: '13px',
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        {results && (
          <div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 14px',
                background: isLive ? '#ECFDF5' : '#FFFBEB',
                border: `1px solid ${isLive ? '#A7F3D0' : '#FDE68A'}`,
                borderRadius: 'var(--radius-sm)',
                marginBottom: '16px',
                fontSize: '12px',
                color: isLive ? '#065F46' : '#92400E',
              }}
            >
              <div>
                <strong>Data Mode: {results.data_mode}</strong> — Source: {results.source}. {results.disclaimer}
              </div>
              <div style={{ fontWeight: 600 }}>{results.total} Offer{results.total === 1 ? '' : 's'}</div>
            </div>

            {results.offers.length === 0 ? (
              <EmptyState
                title="No flight offers returned"
                message="Amadeus returned zero offers for this specific date and route. Note that GDS inventory may not cover low-cost Indian domestic carriers."
              />
            ) : (
              <div className="data-table-wrapper">
                <table className="data-table" aria-label="Flight Offers">
                  <thead>
                    <tr>
                      <th>Carrier</th>
                      <th>Route</th>
                      <th>Departure</th>
                      <th>Stops</th>
                      <th>Class</th>
                      <th>Fare ({isLive ? 'EUR' : 'INR'})</th>
                      <th>INR Estimate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.offers.map((offer, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600 }}>
                          {offer.airline_name || offer.airline_code || 'Airline'}
                        </td>
                        <td>{offer.origin} &rarr; {offer.destination}</td>
                        <td className="mono-num" style={{ fontSize: '12px' }}>
                          {offer.departure_datetime || 'Scheduled'}
                        </td>
                        <td className="mono-num">{offer.stops === 0 ? 'Non-stop' : `${offer.stops} stop`}</td>
                        <td>{offer.cabin_class}</td>
                        <td className="mono-num" style={{ fontWeight: 600 }}>
                          {offer.currency === 'EUR' ? `€${offer.fare.toFixed(2)}` : formatINR(offer.fare)}
                        </td>
                        <td className="mono-num" style={{ fontWeight: 700, color: 'var(--accent-navy)' }}>
                          {offer.fare_inr_estimate ? formatINR(offer.fare_inr_estimate) : formatINR(offer.fare)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {!results && !loading && !error && (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            Select an origin, destination, and travel date above to query live or demo fare offers.
          </div>
        )}
      </div>
    </div>
  );
}
