import type { DashboardData } from '../types';

export function RiskTrend({ trend }: { trend: DashboardData['risk_trend'] }) {
  if (trend.length === 0) return null;
  const width = 800;
  const height = 160;
  const pad = 24;
  const n = trend.length;
  const x = (i: number) => (n <= 1 ? pad : pad + (i * (width - 2 * pad)) / (n - 1));
  const y = (risk: number) => height - pad - (risk / 100) * (height - 2 * pad);
  const points = trend.map((p, i) => `${x(i)},${y(p.overall_risk)}`).join(' ');

  return (
    <section className="panel">
      <h2>Risk trend (chronological)</h2>
      <svg className="trend" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="Risk over time">
        {[0, 31, 61, 81].map((line) => (
          <line key={line} x1={pad} x2={width - pad} y1={y(line)} y2={y(line)} className="grid-line" />
        ))}
        <polyline fill="none" stroke="#4c8eda" strokeWidth="2" points={points} />
        {trend.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.overall_risk)} r="2.5" fill="#4c8eda" />
        ))}
      </svg>
      <p className="axis-note">Gridlines mark the LOW/MEDIUM/HIGH/CRITICAL boundaries (30, 60, 80).</p>
    </section>
  );
}
