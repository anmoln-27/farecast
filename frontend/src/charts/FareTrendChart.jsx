import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import EmptyState from '../components/EmptyState';
import { formatINR, formatDate } from '../utils/formatters';

export default function FareTrendChart({ fares = [], trendData = null }) {
  let chartData = [];

  if (Array.isArray(trendData) && trendData.length > 0) {
    chartData = trendData
      .filter((item) => item.date && item.avgFare)
      .map((item) => ({
        date: item.date,
        avgFare: Math.round(item.avgFare),
        count: item.count || 1,
      }))
      .sort((a, b) => new Date(a.date) - new Date(b.date));
  } else {
    // Aggregate fares by date to get average fare per date
    const dataMap = {};
    fares.forEach((f) => {
      if (!f.travel_date || !f.fare) return;
      const dStr = f.travel_date;
      if (!dataMap[dStr]) {
        dataMap[dStr] = { date: dStr, sum: 0, count: 0 };
      }
      dataMap[dStr].sum += f.fare;
      dataMap[dStr].count += 1;
    });

    chartData = Object.values(dataMap)
      .map((item) => ({
        date: item.date,
        avgFare: Math.round(item.sum / item.count),
        count: item.count,
      }))
      .sort((a, b) => new Date(a.date) - new Date(b.date));
  }

  if (chartData.length === 0) {
    return (
      <EmptyState
        title="No fare trend observations"
        message="No historical observations available for this selection. Adjust filters to view fare movements."
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
            {formatDate(label)}
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            Average Fare: <span className="mono-num" style={{ fontWeight: 600 }}>{formatINR(data.avgFare)}</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
            Observations: {data.count}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => formatDate(d)}
            stroke="#718096"
            fontSize={11}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(val) => `₹${val}`}
            stroke="#718096"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="avgFare"
            stroke="#0F2537"
            strokeWidth={2}
            dot={{ r: 3, fill: '#0F2537', strokeWidth: 0 }}
            activeDot={{ r: 5, fill: '#0F2537' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
