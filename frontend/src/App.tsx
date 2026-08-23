import { useEffect, useState } from 'react';
import type { DashboardData } from './types';
import { SummaryCards } from './components/SummaryCards';
import { RiskDistribution } from './components/RiskDistribution';
import { FindingsBreakdown } from './components/FindingsBreakdown';
import { DimensionMeans } from './components/DimensionMeans';
import { RiskTrend } from './components/RiskTrend';
import { RecentAnalyses } from './components/RecentAnalyses';

export function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('./data.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="page">
      <header className="header">
        <h1>🛡️ AI-SDLC Guardian</h1>
        <span className="subtitle">Pull-request risk dashboard</span>
      </header>

      {error && (
        <p className="empty">
          Could not load <code>data.json</code> ({error}). Run{' '}
          <code>npm run gen-data</code> first.
        </p>
      )}
      {!error && !data && <p className="empty">Loading…</p>}

      {data && (
        <>
          {data.note && <p className="note">{data.note}</p>}
          <SummaryCards totals={data.totals} />
          <div className="grid">
            <RiskDistribution distribution={data.risk_level_distribution} />
            <FindingsBreakdown findings={data.findings_by_severity} />
            <DimensionMeans means={data.dimension_means} />
          </div>
          <RiskTrend trend={data.risk_trend} />
          <RecentAnalyses analyses={data.recent_analyses} />
        </>
      )}
    </div>
  );
}
