import { LEVEL_COLOR, type RecentAnalysis } from '../types';

export function RecentAnalyses({ analyses }: { analyses: RecentAnalysis[] }) {
  return (
    <section className="panel">
      <h2>Recent analyses</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Repository</th>
              <th>PR</th>
              <th>Risk</th>
              <th>Level</th>
              <th>Findings</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {analyses.map((a) => (
              <tr key={a.analysis_id}>
                <td>{a.repository}</td>
                <td>{a.pr_number ? `#${a.pr_number}` : '—'}</td>
                <td>{a.overall_risk}</td>
                <td>
                  <span className="pill" style={{ background: LEVEL_COLOR[a.risk_level] }}>
                    {a.risk_level}
                  </span>
                </td>
                <td>{a.findings_total}</td>
                <td>{a.merge_recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
