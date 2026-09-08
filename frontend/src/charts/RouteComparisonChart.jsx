import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import EmptyState from '../components/EmptyState';
import { formatINR } from '../utils/formatters';

export default function RouteComparisonChart({ fares = [], routeData = null }) {
  let chartData = [];

  if (Array.isArray(routeData) && routeData.length > 0) {
    chartData = routeData
      .filter((item) => item.route && item.avgFare)
      .map((item) => ({
        route: item.route,
        avgFare: Math.round(item.avgFare),
        count: item.count || 1,
      }))
      .sort((a, b) => b.avgFare - a.avgFare)
      .slice(0, 10);
  } else {
    // Aggregate fares by route
    const routeMap = {};
    fares.forEach((f) => {
      if (!f.origin || !f.destination || !f.fare) return;
      const rKey = `${f.origin}-${f.destination}`;
      if (!routeMap[rKey]) {
        routeMap[rKey] = { route: rKey, sum: 0, count: 0 };
      }
      routeMap[rKey].sum += f.fare;
      routeMap[rKey].count += 1;
    });

    chartData = Object.values(routeMap)
      .map((item) => ({
        route: item.route,
        avgFare: Math.round(item.sum / item.count),
        count: item.count,
      }))
      .sort((a, b) => b.avgFare - a.avgFare)
      .slice(0, 10); // Top 10 routes
  }

  if (chartData.length === 0) {
    return (
      <EmptyState
        title="No route fare comparisons"
        message="No observations available for this selection to compare routes."
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
            Route: {data.route}
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
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 10, right: 20, left: 35, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" horizontal={false} />
          <XAxis
            type="number"
            tickFormatter={(val) => `₹${val}`}
            stroke="#718096"
            fontSize={11}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="route"
            stroke="#718096"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="avgFare" fill="#3A506B" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
