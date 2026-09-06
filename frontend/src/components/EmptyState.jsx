import React from 'react';

export default function EmptyState({ title = 'No data available', message = 'No observations available for this selection.' }) {
  return (
    <div className="empty-state">
      <div className="empty-state-title">{title}</div>
      <div className="empty-state-desc">{message}</div>
    </div>
  );
}
