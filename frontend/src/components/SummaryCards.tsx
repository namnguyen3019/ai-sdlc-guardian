import type { DashboardData } from '../types';

export function SummaryCards({ totals }: { totals: DashboardData['totals'] }) {
  const cards = [
    { label: 'PRs analyzed', value: totals.analyses },
    { label: 'Average risk', value: `${totals.average_risk}/100` },
    { label: 'Total findings', value: totals.findings },
  ];
  return (
    <div className="cards">
      {cards.map((c) => (
        <div className="card" key={c.label}>
          <div className="card-value">{c.value}</div>
          <div className="card-label">{c.label}</div>
        </div>
      ))}
    </div>
  );
}
