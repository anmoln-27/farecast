import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts';
import EmptyState from '../components/EmptyState';
import { formatINR } from '../utils/formatters';

export default function AirlineComparisonChart({ fares = [], airlines = [], airlineData = null }) {
  let chartData = [];

  if (Array.isArray(airlineData) && airlineData.length > 0) {
    chartData = airlineData
      .filter((item) => item.airlineCode && item.avgFare)
      .map((item) => {
        const match = airlines.find((a) => a.code === item.airlineCode);
        return {
          airlineCode: item.airlineCode,
          airlineName: match ? match.name : item.airlineCode,
          avgFare: Math.round(item.avgFare),
          count: item.count || 1,
        };
      })
      .sort((a, b) => a.avgFare - b.avgFare);
  } else {
    // Aggregate fares by airline
    const airlineMap = {};
    fares.forEach((f) => {
      if (!f.airline_code || !f.fare) return;
      const code = f.airline_code;
      if (!airlineMap[code]) {
        airlineMap[code] = { code, sum: 0, count: 0 };
      }
      airlineMap[code].sum += f.fare;
      airlineMap[code].count += 1;
    });

    chartData = Object.values(airlineMap)
      .map((item) => {
        const match = airlines.find((a) => a.code === item.code);
        return {
          airlineCode: item.code,
          airlineName: match ? match.name : item.code,
          avgFare: Math.round(item.sum / item.count),
          count: item.count,
        };
      })
      .sort((a, b) => a.avgFare - b.avgFare);
  }

  if (chartData.length === 0) {
    return (
      <EmptyState
        title="No airline fare comparisons"
        message="No observations available for this selection to compare airlines."
      />
    );
  }

  const CustomTooltip = ({ active, payload }) => {
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
            {data.airlineName} ({data.airlineCode})
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
        <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis
            dataKey="airlineCode"
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
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="avgFare" fill="#2C3E50" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill="#2C3E50" />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
