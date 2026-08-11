from conftest import make_file, make_pr

from guardian.analyzers.base import BaseAnalyzer
from guardian.github.pr_loader import load_pr
from guardian.models.findings import Severity
from guardian.models.report import RiskLevel
from guardian.reporting.markdown import GUARDIAN_COMMENT_MARKER, render_markdown
from guardian.services.analysis_service import AnalysisService


def test_risky_pr_end_to_end(fixtures_dir):
    pr = load_pr(fixtures_dir / "risky_payment.diff", fixtures_dir / "meta.json")
    report = AnalysisService().analyze(pr)

    assert report.repository == "acme/shop"
    assert report.pr_number == 42
    assert report.overall_risk > 50
    assert report.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert report.analyzer_failures == []

    rules = {f.rule for f in report.findings}
    assert "SQL_INJECTION_RISK" in rules
    assert "HARDCODED_SECRET" in rules
    assert "AUTH_CHANGE_WITHOUT_TESTS" in rules
    assert "EXCEPTION_HANDLING_REMOVED" in rules
    assert "DEPENDENCY_MANIFEST_CHANGED" in rules

    # Findings are sorted most-severe first.
    assert report.findings[0].severity == Severity.CRITICAL
    ranks = [f.severity.rank for f in report.findings]
    assert ranks == sorted(ranks, reverse=True)


def test_safe_pr_end_to_end(fixtures_dir):
    pr = load_pr(fixtures_dir / "safe_docs.diff")
    report = AnalysisService().analyze(pr)
    assert report.risk_level == RiskLevel.LOW
    assert report.overall_risk <= 30


class ExplodingAnalyzer(BaseAnalyzer):
    name = "exploding"

    def analyze(self, pr, features):
        raise RuntimeError("boom")


def test_analyzer_failure_is_isolated():
    service = AnalysisService()
    service.analyzers.append(ExplodingAnalyzer())
    report = service.analyze(make_pr(make_file("src/app.py", added=[(1, "x = 1")])))
    assert len(report.analyzer_failures) == 1
    assert report.analyzer_failures[0].analyzer == "exploding"
    assert "boom" in report.analyzer_failures[0].error


def test_markdown_report_renders(fixtures_dir):
    pr = load_pr(fixtures_dir / "risky_payment.diff", fixtures_dir / "meta.json")
    report = AnalysisService().analyze(pr)
    rendered = render_markdown(report)
    assert rendered.startswith(GUARDIAN_COMMENT_MARKER)
    assert f"Overall Risk: {report.overall_risk}/100" in rendered
    assert "SQL_INJECTION_RISK" in rendered
    assert "Merge recommendation" in rendered
    assert "Why this score" in rendered
