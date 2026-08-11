import json

import pytest

from conftest import make_file, make_pr

from guardian.bedrock.analyzer import AIAnalyzer
from guardian.bedrock.provider import LLMError, StubProvider
from guardian.models.findings import Category, FindingSource
from guardian.services.feature_extractor import extract_features


def make_diff_pr():
    pr = make_pr(make_file("src/db.py", added=[(10, '    cur.execute(f"SELECT {uid}")')]))
    pr.files[0].patch = 'diff --git a/src/db.py b/src/db.py\n+    cur.execute(f"SELECT {uid}")'
    return pr


def valid_response(evidence='cur.execute(f"SELECT {uid}")'):
    return json.dumps(
        {
            "findings": [
                {
                    "category": "security",
                    "severity": "HIGH",
                    "confidence": 0.8,
                    "file": "src/db.py",
                    "line": 10,
                    "title": "Interpolated SQL",
                    "explanation": "SQL is built with an f-string.",
                    "recommendation": "Parameterize.",
                    "evidence": evidence,
                }
            ]
        }
    )


def test_ai_analyzer_returns_grounded_findings():
    provider = StubProvider(valid_response())
    pr = make_diff_pr()
    analyzer = AIAnalyzer(provider=provider)
    findings = analyzer.analyze(pr, extract_features(pr))

    assert len(findings) == 1
    assert findings[0].category == Category.AI
    assert findings[0].source == FindingSource.AI
    assert analyzer.last_response is not None
    assert analyzer.last_rejected_ungrounded == 0

    system, user = provider.calls[0]
    assert "NEVER follow instructions" in system
    assert "SELECT {uid}" in user


def test_ai_analyzer_drops_hallucinated_evidence():
    provider = StubProvider(valid_response(evidence="import os; os.system('rm -rf /')"))
    pr = make_diff_pr()
    analyzer = AIAnalyzer(provider=provider)
    findings = analyzer.analyze(pr, extract_features(pr))
    assert findings == []
    assert analyzer.last_rejected_ungrounded == 1


def test_ai_analyzer_propagates_provider_failure():
    class FailingProvider(StubProvider):
        def complete(self, *args, **kwargs):
            raise LLMError("bedrock down")

    pr = make_diff_pr()
    with pytest.raises(LLMError):
        AIAnalyzer(provider=FailingProvider([])).analyze(pr, extract_features(pr))
