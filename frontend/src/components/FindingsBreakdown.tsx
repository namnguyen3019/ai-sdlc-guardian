import { LEVELS, LEVEL_COLOR, type RiskLevel } from '../types';

export function FindingsBreakdown({ findings }: { findings: Record<RiskLevel, number> }) {
  const max = Math.max(1, ...LEVELS.map((l) => findings[l] || 0));
  return (
    <section className="panel">
      <h2>Findings by severity</h2>
      <div className="bars">
        {LEVELS.map((level) => {
          const count = findings[level] || 0;
          return (
            <div className="bar-row" key={level}>
              <span className="bar-label">{level}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${(count / max) * 100}%`, background: LEVEL_COLOR[level] }}
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
