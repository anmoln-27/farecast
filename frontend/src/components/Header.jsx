import React from 'react';

export default function Header({ liveStatus, activeTab, onTabChange }) {
  // Mode label handling from /api/live/status
  const modeLabel = liveStatus?.mode_label || (liveStatus?.demo_mode ? 'DEMO' : 'HISTORICAL');
  
  let statusClass = 'historical';
  if (modeLabel.includes('LIVE')) {
    statusClass = 'live';
  } else if (modeLabel.includes('DEMO')) {
    statusClass = 'demo';
  }

  const tabs = [
    { id: 'overview', label: 'Market Overview' },
    { id: 'forecast', label: 'Fare Forecast' },
    { id: 'signals', label: 'Market Signals' },
    { id: 'context', label: 'DGCA & MoSPI Context' },
    { id: 'live', label: 'Live Amadeus Search' },
  ];

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="brand-group">
          <span className="brand-name">FARECAST</span>
          <span className="brand-subtitle">India Airfare Intelligence</span>
        </div>

        <nav style={{ display: 'flex', gap: '8px' }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              style={{
                background: activeTab === tab.id ? 'var(--bg-subtle)' : 'transparent',
                border: activeTab === tab.id ? '1px solid var(--border-darker)' : '1px solid transparent',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: activeTab === tab.id ? '600' : '500',
                color: activeTab === tab.id ? 'var(--accent-navy)' : 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="header-controls">
          <div className={`status-indicator ${statusClass}`} title={liveStatus?.message || 'Data Mode'}>
            <span className="status-dot"></span>
            <span>DATA MODE: {modeLabel}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
