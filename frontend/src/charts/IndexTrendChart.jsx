import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import EmptyState from '../components/EmptyState';
import { formatPeriod } from '../utils/formatters';

export default function IndexTrendChart({ indexRecords = [] }) {
  // Sort chronologically by period
  const sorted = [...indexRecords]
    .filter((r) => r.period && r.index_value !== null && !isNaN(r.index_value))
    .sort((a, b) => a.period.localeCompare(b.period));

  if (sorted.length === 0) {
    return (
      <EmptyState
        title="No index observations"
        message="No prototype index records available for this selection. Calculate index periods to view trend."
      />
    );
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-darker)',
            padding: '8px 12px',
            fontSize: '12px',
            borderRadius: '4px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.08)',
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--accent-navy)', marginBottom: '4px' }}>
            Period: {formatPeriod(label)}
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            Index Value: <span className="mono-num" style={{ fontWeight: 700 }}>{Number(data.index_value).toFixed(1)}</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '2px' }}>
            Baseline: 100.0 ({data.baseline_period || 'Baseline Period'})
          </div>
          {data.route && (
            <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
              Route: {data.route}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={sorted} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis
            dataKey="period"
            tickFormatter={(p) => formatPeriod(p)}
            stroke="#718096"
            fontSize={11}
            tickLine={false}
          />
          <YAxis
            stroke="#718096"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            domain={[80, 140]}
          />
          <ReferenceLine
            y={100}
            stroke="#94A3B8"
            strokeDasharray="4 4"
            label={{ value: 'Baseline (100.0)', position: 'top', fill: '#64748B', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="index_value"
            stroke="#1E3A8A"
            strokeWidth={2}
            dot={{ r: 4, fill: '#1E3A8A', strokeWidth: 0 }}
            activeDot={{ r: 6, fill: '#1E3A8A' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
