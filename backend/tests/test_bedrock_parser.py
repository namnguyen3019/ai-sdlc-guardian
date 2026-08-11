import json

import pytest

from guardian.bedrock.parser import extract_json, parse_findings
from guardian.models.findings import Category, FindingSource, Severity

DIFF = """diff --git a/src/db.py b/src/db.py
--- a/src/db.py
+++ b/src/db.py
@@ -10,3 +10,3 @@
-    cur.execute(query, params)
+    cur.execute(f"SELECT * FROM users WHERE id = {uid}")
+    conn.autocommit = True
"""


def ai_finding(**overrides):
    base = {
        "category": "security",
        "severity": "CRITICAL",
        "confidence": 0.9,
        "file": "src/db.py",
        "line": 10,
        "title": "SQL injection",
        "explanation": "User input reaches SQL.",
        "recommendation": "Use parameters.",
        "evidence": 'cur.execute(f"SELECT * FROM users WHERE id = {uid}")',
    }
    base.update(overrides)
    return base


def test_extract_json_plain_fenced_and_prose():
    payload = {"findings": []}
    assert extract_json(json.dumps(payload)) == payload
    assert extract_json(f"```json\n{json.dumps(payload)}\n```") == payload
    assert extract_json(f"Here is my analysis:\n{json.dumps(payload)}\nHope that helps!") == payload
    with pytest.raises(ValueError):
        extract_json("no json here at all")


def test_grounded_finding_survives():
    result = parse_findings(json.dumps({"findings": [ai_finding()]}), DIFF)
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.category == Category.AI
    assert finding.source == FindingSource.AI
    assert finding.severity == Severity.CRITICAL
    assert finding.rule == "AI_SECURITY"
    assert finding.title == "SQL injection"
    assert finding.line == 10


def test_ungrounded_finding_is_dropped():
    fabricated = ai_finding(evidence="os.system(user_supplied_command)  # not in the diff")
    result = parse_findings(json.dumps({"findings": [ai_finding(), fabricated]}), DIFF)
    assert len(result.findings) == 1
    assert result.rejected_ungrounded == 1


def test_missing_or_short_evidence_is_dropped():
    result = parse_findings(
        json.dumps({"findings": [ai_finding(evidence=""), ai_finding(evidence="a"), {"severity": "HIGH"}]}),
        DIFF,
    )
    assert result.findings == []
    assert result.rejected_ungrounded == 3


def test_evidence_matching_ignores_whitespace_and_diff_prefix():
    tolerant = ai_finding(evidence='+    cur.execute(f"SELECT * FROM users   WHERE id = {uid}")')
    result = parse_findings(json.dumps({"findings": [tolerant]}), DIFF)
    assert len(result.findings) == 1


def test_malformed_findings_are_counted_not_fatal():
    bad_severity = ai_finding(severity="CATASTROPHIC")
    missing_reco = ai_finding(recommendation="")
    result = parse_findings(
        json.dumps({"findings": [ai_finding(), bad_severity, missing_reco, "just a string"]}),
        DIFF,
    )
    assert len(result.findings) == 1
    assert result.rejected_malformed == 3


def test_confidence_clamped_and_unknown_category_defaults():
    raw = ai_finding(confidence=7.5, category="vibes")
    result = parse_findings(json.dumps({"findings": [raw]}), DIFF)
    assert result.findings[0].confidence == 1.0
    assert result.findings[0].rule == "AI_CORRECTNESS"


def test_no_findings_response():
    result = parse_findings('{"findings": []}', DIFF)
    assert result.findings == []
    assert result.rejected_total == 0


def test_unparseable_response_raises():
    with pytest.raises(ValueError):
        parse_findings("I refuse to answer in JSON", DIFF)
    with pytest.raises(ValueError):
        parse_findings('{"not_findings": 1}', DIFF)
