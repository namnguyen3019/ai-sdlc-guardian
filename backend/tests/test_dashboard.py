from datetime import datetime, timezone

from guardian.dashboard import from_dynamodb_items, from_reports, summarize
from guardian.github.pr_loader import load_pr
from guardian.services.analysis_service import AnalysisService


def test_from_reports_shape(fixtures_dir):
    risky = AnalysisService().analyze(load_pr(fixtures_dir / "risky_payment.diff", fixtures_dir / "meta.json"))
    safe = AnalysisService().analyze(load_pr(fixtures_dir / "safe_docs.diff"))
    data = from_reports([risky, safe])

    assert data["totals"]["analyses"] == 2
    assert 0 <= data["totals"]["average_risk"] <= 100
    assert sum(data["risk_level_distribution"].values()) == 2
    assert set(data["risk_level_distribution"]) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert len(data["recent_analyses"]) == 2
    assert len(data["risk_trend"]) == 2


def test_summarize_aggregates_and_orders():
    items = [
        {
            "analysis_id": "a", "repository": "acme/x", "pr_number": 1,
            "timestamp": "2026-08-10T00:00:00+00:00", "overall_risk": 20, "risk_level": "LOW",
            "findings_total": 1, "findings_by_severity": {"LOW": 1}, "score_security": 10,
        },
        {
            "analysis_id": "b", "repository": "acme/x", "pr_number": 2,
            "timestamp": "2026-08-11T00:00:00+00:00", "overall_risk": 90, "risk_level": "CRITICAL",
            "findings_total": 3, "findings_by_severity": {"CRITICAL": 2, "HIGH": 1}, "score_security": 90,
        },
    ]
    data = summarize(items)
    assert data["totals"]["average_risk"] == 55.0
    assert data["totals"]["findings"] == 4
    assert data["risk_level_distribution"] == {"LOW": 1, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 1}
    assert data["findings_by_severity"]["CRITICAL"] == 2
    assert data["dimension_means"]["score_security"] == 50.0
    # recent_analyses is newest-first
    assert data["recent_analyses"][0]["analysis_id"] == "b"
    # trend is chronological
    assert [p["overall_risk"] for p in data["risk_trend"]] == [20, 90]


def test_empty_is_safe():
    data = from_dynamodb_items([])
    assert data["totals"] == {"analyses": 0, "average_risk": 0.0, "findings": 0}
    assert data["recent_analyses"] == []
