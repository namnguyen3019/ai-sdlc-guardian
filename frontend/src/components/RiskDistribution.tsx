import { LEVELS, LEVEL_COLOR, type RiskLevel } from '../types';

export function RiskDistribution({ distribution }: { distribution: Record<RiskLevel, number> }) {
  const total = LEVELS.reduce((sum, l) => sum + (distribution[l] || 0), 0) || 1;
  return (
    <section className="panel">
      <h2>Risk level distribution</h2>
      <div className="bars">
        {LEVELS.map((level) => {
          const count = distribution[level] || 0;
          return (
            <div className="bar-row" key={level}>
              <span className="bar-label">{level}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${(count / total) * 100}%`, background: LEVEL_COLOR[level] }}
                />
              </div>
              <span className="bar-count">{count}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
