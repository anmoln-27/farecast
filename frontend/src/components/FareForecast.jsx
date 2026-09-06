import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { formatINR } from '../utils/formatters';

export default function FareForecast({ defaultOrigin = 'DEL', defaultDestination = 'BOM' }) {
  const [params, setParams] = useState({
    origin: defaultOrigin || 'DEL',
    destination: defaultDestination || 'BOM',
    airline: 'IndiGo',
    cabin_class: 'Economy',
    departure_time: 'Morning',
    arrival_time: 'Afternoon',
    stops: 0,
    duration_minutes: 130,
    days_left: 20,
  });

  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState(null);
  const [error, setError] = useState(null);

  const fetchForecast = async (forecastParams) => {
    if (!forecastParams.origin || !forecastParams.destination) return;
    if (forecastParams.origin === forecastParams.destination) {
      setError('Origin and destination cannot be the same.');
      setPrediction(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.getPrediction(forecastParams);
      setPrediction(res);
    } catch (err) {
      setError(err.message || 'Unable to compute forecast.');
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast(params);
  }, []);

  const handleChange = (field, value) => {
    const next = { ...params, [field]: value };
    setParams(next);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    fetchForecast(params);
  };

  return (
    <div className="panel" id="section-fare-forecast">
      <div className="panel-header">
        <div className="panel-title-group">
          <span className="panel-title">FARE FORECAST</span>
          <span className="panel-subtitle">Model-based airfare estimates based on machine learning models</span>
        </div>
        <span
          style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {prediction ? `Pipeline: ${prediction.model}` : 'CatBoost / Ensemble'}
        </span>
      </div>

      <div className="panel-body">
        <form onSubmit={handleSubmit} style={{ marginBottom: '24px' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            <div className="filter-item">
              <label className="filter-label" htmlFor="fc-origin">Origin</label>
              <select
                id="fc-origin"
                className="filter-select"
                value={params.origin}
                onChange={(e) => handleChange('origin', e.target.value)}
              >
                <option value="DEL">Delhi (DEL)</option>
                <option value="BOM">Mumbai (BOM)</option>
                <option value="BLR">Bangalore (BLR)</option>
                <option value="HYD">Hyderabad (HYD)</option>
                <option value="CCU">Kolkata (CCU)</option>
                <option value="MAA">Chennai (MAA)</option>
              </select>
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="fc-dest">Destination</label>
              <select
                id="fc-dest"
                className="filter-select"
                value={params.destination}
                onChange={(e) => handleChange('destination', e.target.value)}
              >
                <option value="BOM">Mumbai (BOM)</option>
                <option value="DEL">Delhi (DEL)</option>
                <option value="BLR">Bangalore (BLR)</option>
                <option value="HYD">Hyderabad (HYD)</option>
                <option value="CCU">Kolkata (CCU)</option>
                <option value="MAA">Chennai (MAA)</option>
              </select>
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="fc-airline">Airline</label>
              <select
                id="fc-airline"
                className="filter-select"
                value={params.airline}
                onChange={(e) => handleChange('airline', e.target.value)}
              >
                <option value="IndiGo">IndiGo</option>
                <option value="Air India">Air India</option>
                <option value="Vistara">Vistara</option>
                <option value="SpiceJet">SpiceJet</option>
                <option value="AirAsia">Air Asia India</option>
                <option value="GO FIRST">Go First</option>
              </select>
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="fc-cabin">Cabin Class</label>
              <select
                id="fc-cabin"
                className="filter-select"
                value={params.cabin_class}
                onChange={(e) => handleChange('cabin_class', e.target.value)}
              >
                <option value="Economy">Economy</option>
                <option value="Business">Business</option>
              </select>
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="fc-days">Days to Flight</label>
              <input
                id="fc-days"
                type="number"
                min="1"
                max="120"
                className="filter-input"
                value={params.days_left}
                onChange={(e) => handleChange('days_left', parseInt(e.target.value, 10) || 1)}
              />
            </div>

            <div className="filter-item">
              <label className="filter-label" htmlFor="fc-stops">Stops</label>
              <select
                id="fc-stops"
                className="filter-select"
                value={params.stops}
                onChange={(e) => handleChange('stops', parseInt(e.target.value, 10))}
              >
                <option value={0}>Non-stop (0)</option>
                <option value={1}>1 Stop</option>
                <option value={2}>2+ Stops</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || params.origin === params.destination}
              id="btn-compute-forecast"
            >
              {loading ? 'Estimating...' : 'Calculate Model Estimate'}
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

        {prediction && (
          <div
            style={{
              background: 'var(--bg-app)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              padding: '20px',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                flexWrap: 'wrap',
                gap: '16px',
                borderBottom: '1px solid var(--border-color)',
                paddingBottom: '16px',
                marginBottom: '16px',
              }}
            >
              <div>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', fontWeight: 600 }}>
                  Estimated Fare (Model-based estimate)
                </div>
                <div
                  style={{
                    fontSize: '28px',
                    fontWeight: 700,
                    color: 'var(--accent-navy)',
                    marginTop: '2px',
                  }}
                  className="mono-num"
                  id="predicted-fare-val"
                >
                  {formatINR(prediction.predicted_fare)}
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', fontWeight: 600 }}>
                  Model-Based Estimated Fare Range
                </div>
                <div
                  style={{
                    fontSize: '16px',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    marginTop: '2px',
                  }}
                  className="mono-num"
                  id="predicted-range-val"
                >
                  {formatINR(prediction.lower_estimate)} — {formatINR(prediction.upper_estimate)}
                </div>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: '12px',
                fontSize: '12px',
                color: 'var(--text-secondary)',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Route Context:</span>{' '}
                <strong>{prediction.route}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Airline / Class:</span>{' '}
                <strong>{prediction.airline} ({prediction.cabin_class})</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Lead Time:</span>{' '}
                <strong>{prediction.days_left} days prior</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Model Uncertainty:</span>{' '}
                <strong>&plusmn;{(prediction.prediction_uncertainty_margin * 100).toFixed(0)}%</strong>
              </div>
            </div>

            <div
              style={{
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid var(--border-color)',
                fontSize: '11px',
                color: 'var(--text-muted)',
                lineHeight: 1.4,
              }}
            >
              <strong>Disclaimer:</strong> {prediction.disclaimer || 'Predictions are model-based estimates based on historical patterns. Actual fares vary based on real-time seat inventory, dynamic pricing, and booking timing.'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
