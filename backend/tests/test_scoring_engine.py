import pytest

from guardian.models.config import GuardianConfig, ScoringWeights
from guardian.models.findings import Category, Finding, Severity
from guardian.models.report import MergeRecommendation, RiskLevel
from guardian.scoring.engine import RiskScoringEngine


def finding(category=Category.SECURITY, severity=Severity.HIGH, confidence=1.0):
    return Finding(
        category=category,
        severity=severity,
        confidence=confidence,
        rule="TEST_RULE",
        reason="test",
        recommendation="test",
    )


def test_no_findings_is_low_risk():
    result = RiskScoringEngine().score([])
    assert result.overall_risk == 0
    assert result.risk_level == RiskLevel.LOW
    assert result.merge_recommendation == MergeRecommendation.APPROVE


def test_weights_renormalized_without_ai():
    result = RiskScoringEngine().score([finding(severity=Severity.CRITICAL)])
    # security weight becomes 0.30/0.90; one CRITICAL at confidence 1.0 = 45 points
    assert result.scores.security == 45
    assert result.weights_used["security"] == pytest.approx(0.3333, abs=1e-3)
    assert "ai_risk" not in result.weights_used
    assert result.overall_risk == 15


def test_dimension_score_capped_at_100():
    findings = [finding(severity=Severity.CRITICAL) for _ in range(5)]
    result = RiskScoringEngine().score(findings)
    assert result.scores.security == 100


def test_confidence_scales_contribution():
    result = RiskScoringEngine().score([finding(severity=Severity.CRITICAL, confidence=0.5)])
    assert result.scores.security == 22  # round(45 * 0.5)


def test_dependency_findings_map_to_change_impact():
    result = RiskScoringEngine().score([finding(category=Category.DEPENDENCY, severity=Severity.MEDIUM)])
    assert result.scores.change_impact == 14
    assert result.scores.security == 0


def test_risk_level_boundaries():
    assert RiskLevel.from_score(0) == RiskLevel.LOW
    assert RiskLevel.from_score(30) == RiskLevel.LOW
    assert RiskLevel.from_score(31) == RiskLevel.MEDIUM
    assert RiskLevel.from_score(60) == RiskLevel.MEDIUM
    assert RiskLevel.from_score(61) == RiskLevel.HIGH
    assert RiskLevel.from_score(80) == RiskLevel.HIGH
    assert RiskLevel.from_score(81) == RiskLevel.CRITICAL
    assert RiskLevel.from_score(100) == RiskLevel.CRITICAL


def test_custom_weights():
    config = GuardianConfig(
        weights=ScoringWeights(security=1.0, testing=0.0, change_impact=0.0, complexity=0.0, ai_risk=0.0)
    )
    result = RiskScoringEngine(config).score(
        [finding(severity=Severity.CRITICAL), finding(severity=Severity.CRITICAL), finding(severity=Severity.CRITICAL)]
    )
    assert result.overall_risk == 100
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.merge_recommendation == MergeRecommendation.BLOCK


def test_explanations_cover_every_dimension():
    result = RiskScoringEngine().score([finding()])
    dims = {e.dimension for e in result.explanations}
    assert dims == {"security", "testing", "change_impact", "complexity", "ai_risk"}
    security = next(e for e in result.explanations if e.dimension == "security")
    assert "TEST_RULE" in security.detail
    ai = next(e for e in result.explanations if e.dimension == "ai_risk")
    assert "not run" in ai.detail


def test_score_is_deterministic():
    findings = [finding(), finding(category=Category.TESTING, severity=Severity.MEDIUM)]
    first = RiskScoringEngine().score(findings)
    second = RiskScoringEngine().score(findings)
    assert first.overall_risk == second.overall_risk
    assert first.scores == second.scores


def test_negative_weights_rejected():
    with pytest.raises(ValueError):
        ScoringWeights(security=-0.1)
