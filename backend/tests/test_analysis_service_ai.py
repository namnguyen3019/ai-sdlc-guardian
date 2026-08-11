import json

from conftest import make_file, make_pr

from guardian.bedrock.provider import LLMError, StubProvider
from guardian.github.pr_loader import load_pr
from guardian.models.config import GuardianConfig
from guardian.services.analysis_service import AnalysisService


def valid_ai_response(evidence: str) -> str:
    return json.dumps(
        {
            "findings": [
                {
                    "category": "concurrency",
                    "severity": "HIGH",
                    "confidence": 0.7,
                    "file": "src/payment/payment_service.py",
                    "title": "Unsafe retry",
                    "explanation": "Charge is retried without idempotency.",
                    "recommendation": "Add an idempotency key.",
                    "evidence": evidence,
                }
            ]
        }
    )


def test_ai_findings_join_the_report(fixtures_dir):
    pr = load_pr(fixtures_dir / "risky_payment.diff", fixtures_dir / "meta.json")
    provider = StubProvider(valid_ai_response('return requests.post(GATEWAY_URL, json={"amount": amount},'))
    report = AnalysisService(ai_provider=provider).analyze(pr)

    ai_findings = [f for f in report.findings if f.rule.startswith("AI_")]
    assert len(ai_findings) == 1
    assert report.ai is not None and report.ai.ran
    assert report.ai.input_tokens > 0
    assert report.scores.ai_risk > 0
    assert "ai_risk" in report.weights_used  # AI weight active, not renormalized away


def test_ai_provider_failure_is_isolated(fixtures_dir):
    class DownProvider(StubProvider):
        def complete(self, *args, **kwargs):
            raise LLMError("region outage")

    pr = load_pr(fixtures_dir / "risky_payment.diff")
    report = AnalysisService(ai_provider=DownProvider([])).analyze(pr)

    assert any(f.analyzer == "ai" for f in report.analyzer_failures)
    assert report.ai is not None and not report.ai.ran
    assert "ai_risk" not in report.weights_used  # weight renormalized away
    assert report.overall_risk > 50  # deterministic analysis still stands


def test_ai_disabled_by_config(fixtures_dir):
    pr = load_pr(fixtures_dir / "safe_docs.diff")
    provider = StubProvider('{"findings": []}')
    config = GuardianConfig(ai_enabled=False)
    report = AnalysisService(config, ai_provider=provider).analyze(pr)
    assert provider.calls == []
    assert report.ai is None


def test_escalation_gate_skips_safe_pr(fixtures_dir):
    config = GuardianConfig(ai_escalation_gate=True)
    provider = StubProvider('{"findings": []}')
    pr = load_pr(fixtures_dir / "safe_docs.diff")
    report = AnalysisService(config, ai_provider=provider).analyze(pr)

    assert provider.calls == []  # the model was never invoked
    assert report.ai is not None
    assert report.ai.skipped_by_gate
    assert "deterministic risk" in report.ai.skip_reason
    assert "ai_risk" not in report.weights_used


def test_escalation_gate_runs_on_risky_pr(fixtures_dir):
    config = GuardianConfig(ai_escalation_gate=True)
    provider = StubProvider('{"findings": []}')
    pr = load_pr(fixtures_dir / "risky_payment.diff")
    report = AnalysisService(config, ai_provider=provider).analyze(pr)

    assert len(provider.calls) == 1  # critical modules force escalation
    assert report.ai is not None and report.ai.ran


def test_gate_escalates_on_churn_alone():
    config = GuardianConfig(ai_escalation_gate=True, ai_gate_max_churn=50)
    provider = StubProvider('{"findings": []}')
    pr = make_pr(make_file("docs_gen.py", added=[(i, f"x{i} = {i}") for i in range(1, 101)]))
    AnalysisService(config, ai_provider=provider).analyze(pr)
    assert len(provider.calls) == 1
