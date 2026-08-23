"""Build dashboard data from analyses.

Two sources, same output shape (the DynamoDB metadata item):

* ``from_reports`` — summarize a list of RiskReport objects (used to generate
  a sample dataset from real Guardian runs over local diffs).
* ``from_dynamodb_items`` — pass through items scanned from the analyses
  table for a live dashboard.

The frontend consumes the JSON this produces; it never talks to AWS directly.
"""

from __future__ import annotations

from collections import Counter

from guardian.models.report import RiskReport


def _item_from_report(report: RiskReport) -> dict:
    severity_counts: dict[str, int] = {}
    for finding in report.findings:
        severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1
    return {
        "analysis_id": report.analysis_id,
        "repository": report.repository,
        "pr_number": report.pr_number,
        "timestamp": report.timestamp.isoformat(),
        "overall_risk": report.overall_risk,
        "risk_level": report.risk_level.value,
        "merge_recommendation": report.merge_recommendation.value,
        "score_security": report.scores.security,
        "score_testing": report.scores.testing,
        "score_change_impact": report.scores.change_impact,
        "score_complexity": report.scores.complexity,
        "score_ai_risk": report.scores.ai_risk,
        "findings_total": len(report.findings),
        "findings_by_severity": severity_counts,
        "duration_ms": report.duration_ms,
    }


def summarize(items: list[dict]) -> dict:
    """Aggregate metadata items into the dashboard payload."""
    items = sorted(items, key=lambda i: str(i.get("timestamp", "")))
    total = len(items)
    risks = [int(i.get("overall_risk", 0)) for i in items]

    level_counts = Counter(str(i.get("risk_level", "")) for i in items)
    severity_totals: Counter = Counter()
    for item in items:
        for severity, count in (item.get("findings_by_severity") or {}).items():
            severity_totals[severity] += int(count)

    dimension_means: dict[str, float] = {}
    for key in ("score_security", "score_testing", "score_change_impact", "score_complexity", "score_ai_risk"):
        values = [int(i.get(key, 0)) for i in items]
        dimension_means[key] = round(sum(values) / len(values), 1) if values else 0.0

    return {
        "generated_from": "guardian-analyses",
        "totals": {
            "analyses": total,
            "average_risk": round(sum(risks) / total, 1) if total else 0.0,
            "findings": sum(int(i.get("findings_total", 0)) for i in items),
        },
        "risk_level_distribution": {
            level: level_counts.get(level, 0) for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        },
        "findings_by_severity": {
            severity: severity_totals.get(severity, 0) for severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        },
        "dimension_means": dimension_means,
        "risk_trend": [
            {"timestamp": str(i.get("timestamp", "")), "overall_risk": int(i.get("overall_risk", 0))}
            for i in items
        ],
        "recent_analyses": [
            {
                "analysis_id": i.get("analysis_id", ""),
                "repository": i.get("repository", ""),
                "pr_number": i.get("pr_number", 0),
                "overall_risk": int(i.get("overall_risk", 0)),
                "risk_level": i.get("risk_level", ""),
                "merge_recommendation": i.get("merge_recommendation", ""),
                "findings_total": int(i.get("findings_total", 0)),
                "timestamp": str(i.get("timestamp", "")),
            }
            for i in reversed(items[-25:])
        ],
    }


def from_reports(reports: list[RiskReport]) -> dict:
    return summarize([_item_from_report(r) for r in reports])


def from_dynamodb_items(items: list[dict]) -> dict:
    return summarize(items)
