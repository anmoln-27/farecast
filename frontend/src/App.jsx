import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import FilterBar from './components/FilterBar';
import IndexSection from './components/IndexSection';
import FareSummary from './components/FareSummary';
import FareTrendChart from './charts/FareTrendChart';
import IndexTrendChart from './charts/IndexTrendChart';
import AirlineComparisonChart from './charts/AirlineComparisonChart';
import RouteComparisonChart from './charts/RouteComparisonChart';
import FareForecast from './components/FareForecast';
import MarketSignals from './components/MarketSignals';
import AviationContext from './components/AviationContext';
import LiveSearchSection from './components/LiveSearchSection';
import LeadTimeElasticityChart from './charts/LeadTimeElasticityChart';
import SectorHeatmap from './charts/SectorHeatmap';
import NsoRbiPortal from './components/NsoRbiPortal';
import { api } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');

  // Metadata
  const [liveStatus, setLiveStatus] = useState(null);
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [routes, setRoutes] = useState([]);
  const [airlines, setAirlines] = useState([]);

  // Active Filters
  const [filters, setFilters] = useState({
    origin: '',
    destination: '',
    travel_date: '',
    airline: '',
    cabin_class: '',
  });

  // Data States
  const [faresData, setFaresData] = useState(null);
  const [indexData, setIndexData] = useState(null);
  const [anomaliesData, setAnomaliesData] = useState([]);
  const [dgcaData, setDgcaData] = useState([]);
  const [cpiData, setCpiData] = useState([]);

  // Loading & Error States
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initial load: Live status, metadata, summary, and foundational records
  useEffect(() => {
    async function init() {
      try {
        const [statusRes, summaryRes, routesRes, airlinesRes, cpiRes, dgcaRes] = await Promise.allSettled([
          api.getLiveStatus(),
          api.getDashboardSummary(),
          api.getRoutes(),
          api.getAirlines(),
          api.getCpi(),
          api.getDgca({ limit: 20 }),
        ]);

        if (statusRes.status === 'fulfilled') setLiveStatus(statusRes.value);
        if (summaryRes.status === 'fulfilled') setDashboardSummary(summaryRes.value);
        if (routesRes.status === 'fulfilled') setRoutes(routesRes.value.data || []);
        if (airlinesRes.status === 'fulfilled') setAirlines(airlinesRes.value.data || []);
        if (cpiRes.status === 'fulfilled') setCpiData(cpiRes.value.data || []);
        if (dgcaRes.status === 'fulfilled') setDgcaData(dgcaRes.value.data || []);
      } catch (err) {
        console.error('Initial metadata fetch failed:', err);
      }
    }
    init();
  }, []);

  // Fetch filtered data
  const fetchData = useCallback(async (currentFilters) => {
    setLoading(true);
    setError(null);

    try {
      // 1. Fetch fares with filters
      const fareParams = {
        limit: 100,
        origin: currentFilters.origin || undefined,
        destination: currentFilters.destination || undefined,
        airline: currentFilters.airline || undefined,
        cabin_class: currentFilters.cabin_class || undefined,
        travel_date_from: currentFilters.travel_date || undefined,
        travel_date_to: currentFilters.travel_date || undefined,
      };

      // 2. Fetch Index
      const fetchIndexPromise = (currentFilters.origin && currentFilters.destination)
        ? api.getRouteIndex(currentFilters.origin, currentFilters.destination).catch(() => ({ data: [] }))
        : api.getIndex({ limit: 100 });

      // 3. Fetch Anomalies
      const anomalyParams = {
        limit: 50,
        route: (currentFilters.origin && currentFilters.destination)
          ? `${currentFilters.origin}-${currentFilters.destination}`
          : undefined,
      };

      const [faresRes, indexRes, anomaliesRes] = await Promise.allSettled([
        api.getFares(fareParams),
        fetchIndexPromise,
        api.getAnomalies(anomalyParams),
      ]);

      if (faresRes.status === 'fulfilled') {
        setFaresData(faresRes.value);
      } else {
        setFaresData({ data: [], meta: { total: 0 } });
      }

      if (indexRes.status === 'fulfilled') {
        setIndexData(indexRes.value);
      } else {
        setIndexData({ data: [], total: 0 });
      }

      if (anomaliesRes.status === 'fulfilled') {
        setAnomaliesData(anomaliesRes.value.data || []);
      } else {
        setAnomaliesData([]);
      }
    } catch (err) {
      setError(err.message || 'Failed to load observations.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Trigger fetch on mount and on filter changes
  useEffect(() => {
    fetchData(filters);
  }, [fetchData]);

  const handleFilterChange = (key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  };

  const handleApply = () => {
    fetchData(filters);
  };

  const handleReset = () => {
    const clean = {
      origin: '',
      destination: '',
      travel_date: '',
      airline: '',
      cabin_class: '',
    };
    setFilters(clean);
    fetchData(clean);
  };

  const selectedRouteCode = (filters.origin && filters.destination)
    ? `${filters.origin}-${filters.destination}`
    : null;

  return (
    <div className="app-container">
      <Header
        liveStatus={liveStatus}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <main className="main-content">
        {/* Global Filter Bar */}
        <FilterBar
          filters={filters}
          onChange={handleFilterChange}
          onApply={handleApply}
          onReset={handleReset}
          routes={routes}
          airlines={airlines}
          loading={loading}
        />

        {error && (
          <div
            style={{
              padding: '12px 16px',
              background: '#FEF2F2',
              color: '#991B1B',
              border: '1px solid #FECACA',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '20px',
              fontSize: '13px',
            }}
          >
            {error}
          </div>
        )}

        {/* Tab 1: Market Overview */}
        {activeTab === 'overview' && (
          <div>
            {/* Prototype Airfare Price Index */}
            <IndexSection
              indexData={indexData}
              selectedRoute={selectedRouteCode}
            />

            {/* Fare Summary KPIs */}
            <FareSummary
              faresData={faresData}
              summaryMeta={dashboardSummary}
            />

            {/* 4 Required Charts Grid */}
            <div className="dashboard-grid">
              {/* Chart A: Fare Trend */}
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title-group">
                    <span className="panel-title">FARE MOVEMENT TREND</span>
                    <span className="panel-subtitle">Average historical fare movement over observation timeline</span>
                  </div>
                </div>
                <div className="panel-body">
                  <FareTrendChart fares={faresData?.data || []} />
                </div>
              </div>

              {/* Chart B: Airfare Price Index Trend */}
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title-group">
                    <span className="panel-title">PROTOTYPE PRICE INDEX TREND</span>
                    <span className="panel-subtitle">Historical index movement against baseline (Base = 100.0)</span>
                  </div>
                </div>
                <div className="panel-body">
                  <IndexTrendChart indexRecords={indexData?.data || []} />
                </div>
              </div>

              {/* Chart C: Airline Fare Comparison */}
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title-group">
                    <span className="panel-title">AIRLINE FARE COMPARISON</span>
                    <span className="panel-subtitle">Average observed fares across domestic carriers</span>
                  </div>
                </div>
                <div className="panel-body">
                  <AirlineComparisonChart
                    fares={faresData?.data || []}
                    airlines={airlines}
                  />
                </div>
              </div>

              {/* Chart D: Route Fare Comparison */}
              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title-group">
                    <span className="panel-title">ROUTE FARE BENCHMARKS</span>
                    <span className="panel-subtitle">Average fare benchmarks across key domestic sectors</span>
                  </div>
                </div>
                <div className="panel-body">
                  <RouteComparisonChart fares={faresData?.data || []} />
                </div>
              </div>
            </div>

            {/* Lead-Time Elasticity Surge Curve */}
            <div style={{ marginTop: '24px' }}>
              <LeadTimeElasticityChart />
            </div>

            {/* Sector Surge Pricing Heatmap */}
            <div style={{ marginTop: '24px' }}>
              <SectorHeatmap />
            </div>

            {/* Inline Forecast Section */}
            <div style={{ marginTop: '24px' }}>
              <FareForecast
                defaultOrigin={filters.origin || 'DEL'}
                defaultDestination={filters.destination || 'BOM'}
              />
            </div>

            {/* Inline Anomaly Section */}
            <div style={{ marginTop: '24px' }}>
              <MarketSignals anomalies={anomaliesData} loading={loading} />
            </div>

            {/* Inline Context Section */}
            <div style={{ marginTop: '24px' }}>
              <AviationContext
                dgcaRecords={dgcaData}
                dgcaSummary={dashboardSummary}
                cpiRecords={cpiData}
              />
            </div>
          </div>
        )}

        {/* Tab: Surge & Elasticity Heatmaps */}
        {activeTab === 'elasticity' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '12px' }}>
            <LeadTimeElasticityChart />
            <SectorHeatmap />
          </div>
        )}

        {/* Tab: Dedicated NSO & RBI Regulatory Intelligence Portal */}
        {activeTab === 'regulatory' && (
          <div style={{ marginTop: '12px' }}>
            <NsoRbiPortal />
          </div>
        )}

        {/* Tab: Dedicated Fare Forecast */}
        {activeTab === 'forecast' && (
          <div style={{ marginTop: '12px' }}>
            <FareForecast
              defaultOrigin={filters.origin || 'DEL'}
              defaultDestination={filters.destination || 'BOM'}
            />
          </div>
        )}

        {/* Tab: Dedicated Market Signals */}
        {activeTab === 'signals' && (
          <div style={{ marginTop: '12px' }}>
            <MarketSignals anomalies={anomaliesData} loading={loading} />
          </div>
        )}

        {/* Tab: DGCA & MoSPI Context */}
        {activeTab === 'context' && (
          <div style={{ marginTop: '12px' }}>
            <AviationContext
              dgcaRecords={dgcaData}
              dgcaSummary={dashboardSummary}
              cpiRecords={cpiData}
            />
          </div>
        )}

        {/* Tab: Live Amadeus Search */}
        {activeTab === 'live' && (
          <div style={{ marginTop: '12px' }}>
            <LiveSearchSection liveStatus={liveStatus} />
          </div>
        )}
      </main>

      <footer className="app-footer">
        <div className="footer-inner">
          <div>
            <strong>FARECAST — India Airfare Intelligence</strong> &bull; SIH 26056 Research Prototype
          </div>
          <div>
            Prototype Airfare Price Index is computed for research purposes and is <strong>not</strong> an official Government of India statistic.
          </div>
        </div>
      </footer>
    </div>
  );
}
