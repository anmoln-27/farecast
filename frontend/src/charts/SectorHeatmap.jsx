import React, { useState, useEffect } from 'react';
import { formatINR } from '../utils/formatters';
import { Grid, Flame, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

const DEFAULT_SECTOR_DATA = [
  {
    route: 'DEL-BOM',
    originCity: 'Delhi',
    destCity: 'Mumbai',
    dgcaWeight: '18.5%',
    fares: { 'T+45': 3850, 'T+30': 4420, 'T+15': 5580, 'T+7': 8080, 'T+1': 12510 },
  },
  {
    route: 'DEL-BLR',
    originCity: 'Delhi',
    destCity: 'Bengaluru',
    dgcaWeight: '14.2%',
    fares: { 'T+45': 4620, 'T+30': 5310, 'T+15': 6700, 'T+7': 9700, 'T+1': 15020 },
  },
  {
    route: 'BOM-BLR',
    originCity: 'Mumbai',
    destCity: 'Bengaluru',
    dgcaWeight: '10.1%',
    fares: { 'T+45': 3220, 'T+30': 3700, 'T+15': 4670, 'T+7': 6760, 'T+1': 10465 },
  },
  {
    route: 'DEL-CCU',
    originCity: 'Delhi',
    destCity: 'Kolkata',
    dgcaWeight: '8.6%',
    fares: { 'T+45': 4220, 'T+30': 4850, 'T+15': 6120, 'T+7': 8860, 'T+1': 13715 },
  },
];

const WINDOWS = ['T+45', 'T+30', 'T+15', 'T+7', 'T+1'];

function getIntensityColor(fare, baseFare) {
  if (!fare || !baseFare) return { bg: '#F7FAFC', text: '#718096', border: '#E2E8F0' };
  const multiplier = fare / baseFare;
  if (multiplier <= 1.05) return { bg: '#EBF8FF', text: '#2B6CB0', border: '#BEE3F8' };
  if (multiplier <= 1.25) return { bg: '#E6FFFA', text: '#234E52', border: '#B2F5EA' };
  if (multiplier <= 1.65) return { bg: '#FEFCBF', text: '#744210', border: '#FAF089' };
  if (multiplier <= 2.40) return { bg: '#FEEBC8', text: '#7B341E', border: '#FBD38D' };
  return { bg: '#FED7D7', text: '#9B2C2C', border: '#FEB2B2' };
}

export default function SectorHeatmap() {
  const [hoveredCell, setHoveredCell] = useState(null);
  const [sectors, setSectors] = useState(DEFAULT_SECTOR_DATA);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function fetchMatrix() {
      setLoading(true);
      try {
        const res = await api.getSectorMatrix();
        const matrixData = res?.data || res?.sectors;
        if (isMounted && Array.isArray(matrixData) && matrixData.length > 0) {
          setSectors(matrixData);
        }
      } catch (err) {
        console.error('Failed to load sector heatmap matrix:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    fetchMatrix();
    return () => { isMounted = false; };
  }, []);

  return (
    <div style={{ background: 'var(--bg-surface, #ffffff)', borderRadius: '8px', padding: '20px', border: '1px solid var(--border-darker, #E2E8F0)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--accent-navy, #0F2537)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Flame size={18} color="#DD6B20" />
            Domestic Sector Surge Pricing Heatmap
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-secondary, #718096)' }}>
            Empirical sector matrix across domestic traffic routes and advance-purchase windows
          </p>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#718096' }}>
          <span>Saver (1.0x)</span>
          <span style={{ width: '14px', height: '14px', borderRadius: '3px', background: '#EBF8FF', border: '1px solid #BEE3F8' }} />
          <span style={{ width: '14px', height: '14px', borderRadius: '3px', background: '#E6FFFA', border: '1px solid #B2F5EA' }} />
          <span style={{ width: '14px', height: '14px', borderRadius: '3px', background: '#FEFCBF', border: '1px solid #FAF089' }} />
          <span style={{ width: '14px', height: '14px', borderRadius: '3px', background: '#FEEBC8', border: '1px solid #FBD38D' }} />
          <span style={{ width: '14px', height: '14px', borderRadius: '3px', background: '#FED7D7', border: '1px solid #FEB2B2' }} />
          <span>Surge (3.2x+)</span>
        </div>
      </div>

      {/* Heatmap Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '4px', fontSize: '12px' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '8px 12px', color: '#4A5568', fontWeight: 600 }}>Sector Route</th>
              <th style={{ textAlign: 'center', padding: '8px 12px', color: '#4A5568', fontWeight: 600 }}>Prototype Ref. Weight</th>
              {WINDOWS.map((win) => (
                <th key={win} style={{ textAlign: 'center', padding: '8px 12px', color: '#4A5568', fontWeight: 600 }}>
                  {win} Window
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sectors.map((sector) => {
              const baseFare = sector.fares ? (sector.fares['T+45'] || sector.fares['T+30'] || sector.fares['T+15'] || 1) : 1;
              return (
                <tr key={sector.route}>
                  <td style={{ padding: '8px 12px', fontWeight: 600, color: '#0F2537', background: '#F7FAFC', borderRadius: '4px' }}>
                    {sector.route} <span style={{ fontSize: '11px', fontWeight: 400, color: '#718096' }}>({sector.originCity} ⇄ {sector.destCity})</span>
                  </td>
                  <td style={{ textAlign: 'center', padding: '8px 12px', fontWeight: 600, color: '#2B6CB0', background: '#F7FAFC', borderRadius: '4px' }}>
                    {sector.dgcaWeight}
                  </td>
                  {WINDOWS.map((win) => {
                    const fare = sector.fares ? sector.fares[win] : null;
                    const hasData = fare != null && !isNaN(fare) && Number(fare) > 0;
                    const colorStyle = hasData ? getIntensityColor(fare, baseFare) : { bg: '#F8FAFC', text: '#94A3B8', border: '#E2E8F0' };
                    const mult = hasData && baseFare > 0 ? (fare / baseFare).toFixed(2) : null;
                    return (
                      <td
                        key={win}
                        onMouseEnter={() => hasData && setHoveredCell({ sector: sector.route, win, fare, mult })}
                        onMouseLeave={() => setHoveredCell(null)}
                        style={{
                          textAlign: 'center',
                          padding: '10px 8px',
                          borderRadius: '4px',
                          background: colorStyle.bg,
                          color: colorStyle.text,
                          border: `1px solid ${colorStyle.border}`,
                          fontWeight: 700,
                          cursor: hasData ? 'pointer' : 'default',
                          transition: 'transform 0.15s ease',
                        }}
                      >
                        {hasData ? (
                          <>
                            <div>{formatINR(fare)}</div>
                            <div style={{ fontSize: '10px', opacity: 0.85, fontWeight: 500 }}>{mult}x base</div>
                          </>
                        ) : (
                          <>
                            <div style={{ fontSize: '14px', color: '#94A3B8', fontWeight: 600 }}>—</div>
                            <div style={{ fontSize: '9px', color: '#94A3B8', fontWeight: 500 }}>No obs</div>
                          </>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hoveredCell && (
        <div style={{ marginTop: '12px', padding: '8px 14px', background: '#EDF2F7', borderRadius: '6px', fontSize: '12px', color: '#2D3748', display: 'flex', justifyContent: 'space-between' }}>
          <span><strong>{hoveredCell.sector}</strong> at <strong>{hoveredCell.win}</strong> advance booking</span>
          <span>Average Gross Fare: <strong>{formatINR(hoveredCell.fare)}</strong></span>
          <span>Dynamic Surge: <strong>{hoveredCell.mult}x of T+45 saver</strong></span>
        </div>
      )}
    </div>
  );
}
