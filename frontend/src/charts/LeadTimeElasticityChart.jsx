import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  AreaChart,
  Area,
} from 'recharts';
import { formatINR } from '../utils/formatters';
import { TrendingUp, Layers, Info } from 'lucide-react';

import { api } from '../services/api';

const DEFAULT_ROUTE_DATA = {
  'DEL-BOM': [
    { window: 'T+45', days: 45, total: 3850, base: 2520, taxes: 630, udf: 350, fee: 350, surge: '1.0x' },
    { window: 'T+30', days: 30, total: 4420, base: 2930, taxes: 790, udf: 350, fee: 350, surge: '1.15x' },
    { window: 'T+15', days: 15, total: 5580, base: 3760, taxes: 1120, udf: 350, fee: 350, surge: '1.45x' },
    { window: 'T+7', days: 7, total: 8080, base: 5560, taxes: 1820, udf: 350, fee: 350, surge: '2.10x' },
    { window: 'T+1', days: 1, total: 12510, base: 8750, taxes: 3060, udf: 350, fee: 350, surge: '3.25x' },
  ],
};

export default function LeadTimeElasticityChart({ selectedRouteProp }) {
  const [selectedRoute, setSelectedRoute] = useState(selectedRouteProp || 'DEL-BOM');
  const [viewMode, setViewMode] = useState('curve'); // 'curve' | 'disaggregated'
  const [routesData, setRoutesData] = useState(DEFAULT_ROUTE_DATA);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadElasticity() {
      setLoading(true);
      try {
        const res = await api.getLeadTimeElasticity();
        if (isMounted && res?.data && Object.keys(res.data).length > 0) {
          setRoutesData(res.data);
          const initialRoute = selectedRouteProp && res.data[selectedRouteProp]
            ? selectedRouteProp
            : (res.data[selectedRoute] ? selectedRoute : Object.keys(res.data)[0]);
          setSelectedRoute(initialRoute);
        }
      } catch (err) {
        console.error('Failed to load elasticity data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadElasticity();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    if (selectedRouteProp && routesData[selectedRouteProp]) {
      setSelectedRoute(selectedRouteProp);
    }
  }, [selectedRouteProp, routesData]);

  const availableRoutes = Array.from(new Set(Object.keys(routesData))).sort();
  const data = routesData[selectedRoute] || routesData[availableRoutes[0]] || DEFAULT_ROUTE_DATA['DEL-BOM'];
  const t45 = data[0]?.total || 1;
  const t1 = data[data.length - 1]?.total || t45;
  const surgePct = Math.round(((t1 - t45) / t45) * 100);
  const surgeMultiple = t45 > 0 ? (t1 / t45).toFixed(2) + 'x' : '1.00x';

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const item = payload[0].payload;
      return (
        <div
          style={{
            background: '#ffffff',
            border: '1px solid #E2E8F0',
            padding: '10px 14px',
            fontSize: '12px',
            borderRadius: '6px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          }}
        >
          <div style={{ fontWeight: 700, color: '#0F2537', marginBottom: '6px' }}>
            Advance Window: {item.window} ({item.days} days prior)
          </div>
          <div style={{ color: '#2B6CB0', fontWeight: 600, marginBottom: '4px' }}>
            Total Fare: {formatINR(item.total)} ({item.surge || '1.0x'} base)
          </div>
          {item.observation_count && (
            <div style={{ color: '#718096', fontSize: '11px', marginBottom: '4px' }}>
              Observations: {item.observation_count} flights
            </div>
          )}
          <div style={{ color: '#4A5568', fontSize: '11px' }}>Base Tariff (Est.): {formatINR(item.base)}</div>
          <div style={{ color: '#4A5568', fontSize: '11px' }}>Taxes & GST (Est.): {formatINR(item.taxes)}</div>
          <div style={{ color: '#4A5568', fontSize: '11px' }}>Airport UDF: {formatINR(item.udf)}</div>
          <div style={{ color: '#4A5568', fontSize: '11px' }}>Web Conv. Fee: {formatINR(item.fee)}</div>
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ background: 'var(--bg-surface, #ffffff)', borderRadius: '8px', padding: '20px', border: '1px solid var(--border-darker, #E2E8F0)' }}>
      {/* Header controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--accent-navy, #0F2537)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={18} color="#2B6CB0" />
            Lead-Time Elasticity & Advance Purchase Surge Curve
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-secondary, #718096)' }}>
            Empirical dynamic pricing multiplier across mandatory MoSPI windows (T+45 → T+1)
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="elasticity-route-dropdown" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #4A5568)' }}>
            Sector:
          </label>
          <select
            id="elasticity-route-dropdown"
            className="filter-select"
            value={selectedRoute}
            onChange={(e) => setSelectedRoute(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #CBD5E0',
              fontSize: '13px',
              fontWeight: 600,
              color: '#0F2537',
              backgroundColor: '#FFFFFF',
              minWidth: '130px',
              cursor: 'pointer',
            }}
          >
            {availableRoutes.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          <div style={{ display: 'flex', background: '#EDF2F7', borderRadius: '6px', padding: '2px' }}>
            <button
              onClick={() => setViewMode('curve')}
              style={{
                padding: '4px 10px',
                border: 'none',
                background: viewMode === 'curve' ? '#ffffff' : 'transparent',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 600,
                color: viewMode === 'curve' ? '#2B6CB0' : '#4A5568',
                cursor: 'pointer',
                boxShadow: viewMode === 'curve' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              Surge Curve
            </button>
            <button
              onClick={() => setViewMode('disaggregated')}
              style={{
                padding: '4px 10px',
                border: 'none',
                background: viewMode === 'disaggregated' ? '#ffffff' : 'transparent',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 600,
                color: viewMode === 'disaggregated' ? '#2B6CB0' : '#4A5568',
                cursor: 'pointer',
                boxShadow: viewMode === 'disaggregated' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              Fare Breakdown
            </button>
          </div>
        </div>
      </div>

      {/* KPI highlight strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div style={{ background: '#F7FAFC', padding: '10px 14px', borderRadius: '6px', borderLeft: '3px solid #2B6CB0' }}>
          <div style={{ fontSize: '11px', color: '#718096', textTransform: 'uppercase', fontWeight: 600 }}>T+45 Early Bird Base</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: '#0F2537' }}>{formatINR(t45)}</div>
          <div style={{ fontSize: '11px', color: '#38A169' }}>Promotional Saver Bucket</div>
        </div>

        <div style={{ background: '#F7FAFC', padding: '10px 14px', borderRadius: '6px', borderLeft: '3px solid #DD6B20' }}>
          <div style={{ fontSize: '11px', color: '#718096', textTransform: 'uppercase', fontWeight: 600 }}>T+1 Spot Surge Fare</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: '#0F2537' }}>{formatINR(t1)}</div>
          <div style={{ fontSize: '11px', color: '#E53E3E' }}>+{surgePct}% Dynamic Premium</div>
        </div>

        <div style={{ background: '#F7FAFC', padding: '10px 14px', borderRadius: '6px', borderLeft: '3px solid #319795' }}>
          <div style={{ fontSize: '11px', color: '#718096', textTransform: 'uppercase', fontWeight: 600 }}>Elasticity Surge Multiple</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: '#0F2537' }}>{surgeMultiple}</div>
          <div style={{ fontSize: '11px', color: '#718096' }}>Peak yield management ratio</div>
        </div>
      </div>

      {/* Chart visualization */}
      <div style={{ width: '100%', height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          {viewMode === 'curve' ? (
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <defs>
                <linearGradient id="surgeGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2B6CB0" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#2B6CB0" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="window" stroke="#718096" fontSize={12} tickLine={false} />
              <YAxis tickFormatter={(v) => `₹${v}`} stroke="#718096" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="total" stroke="#2B6CB0" strokeWidth={3} fillOpacity={1} fill="url(#surgeGradient)" />
            </AreaChart>
          ) : (
            <BarChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="window" stroke="#718096" fontSize={12} tickLine={false} />
              <YAxis tickFormatter={(v) => `₹${v}`} stroke="#718096" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="top" height={36} iconType="circle" />
              <Bar dataKey="base" name="Base Fare" stackId="a" fill="#2B6CB0" />
              <Bar dataKey="taxes" name="Taxes & Surcharges" stackId="a" fill="#4299E1" />
              <Bar dataKey="udf" name="Airport UDF" stackId="a" fill="#63B3ED" />
              <Bar dataKey="fee" name="Convenience Fee" stackId="a" fill="#BEE3F8" />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      <div style={{ marginTop: '12px', fontSize: '11px', color: '#718096', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Info size={14} />
        Data normalized across 5 mandatory advance purchase windows (T+1 to T+45) conforming to DGCA and MoSPI statistical price index requirements.
      </div>
    </div>
  );
}
