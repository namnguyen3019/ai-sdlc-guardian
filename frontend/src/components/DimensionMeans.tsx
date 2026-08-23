const LABELS: Record<string, string> = {
  score_security: 'Security',
  score_testing: 'Testing',
  score_change_impact: 'Change impact',
  score_complexity: 'Complexity',
  score_ai_risk: 'AI risk',
};

export function DimensionMeans({ means }: { means: Record<string, number> }) {
  return (
    <section className="panel">
      <h2>Mean score by dimension</h2>
      <div className="bars">
        {Object.entries(LABELS).map(([key, label]) => {
          const value = means[key] ?? 0;
          return (
            <div className="bar-row" key={key}>
              <span className="bar-label wide">{label}</span>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${value}%`, background: '#4c8eda' }} />
              </div>
              <span className="bar-count">{value}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
