"""Parse and validate model output into ``Finding`` objects.

Two guarantees matter here and both are enforced by the application, not
requested politely from the model:

1. **Schema validity.** Anything that does not fit the expected shape is
   dropped rather than half-trusted.
2. **Evidence grounding.** A finding survives only if its quoted evidence
   actually occurs in the diff that was sent. This is what stops the model
   inventing code that does not exist.
"""

from __future__ import annotations

import json
import logging
import re

from guardian.models.findings import Category, Finding, FindingSource, Severity

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)
_WS = re.compile(r"\s+")

# Sub-categories the model may report. All map to Category.AI for scoring —
# the label is preserved in the rule id so the report stays informative.
_KNOWN_CATEGORIES = {
    "security", "correctness", "reliability", "testing", "maintainability",
    "auth", "database", "api", "concurrency", "error_handling",
}


class ParseResult:
    """Findings that survived validation, plus why the others did not."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.rejected_ungrounded: int = 0
        self.rejected_malformed: int = 0

    @property
    def rejected_total(self) -> int:
        return self.rejected_ungrounded + self.rejected_malformed


def _normalize(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response.

    Tolerates markdown fences and leading/trailing prose, because a strict
    parse failure would discard an otherwise good analysis.
    """
    cleaned = _FENCE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model response")
    return json.loads(cleaned[start : end + 1])


def build_evidence_corpus(diff_text: str) -> str:
    """Normalized text used to verify that evidence really came from the diff."""
    return _normalize(diff_text)


def parse_findings(response_text: str, diff_text: str) -> ParseResult:
    """Validate model output against the schema and the supplied diff."""
    result = ParseResult()
    try:
        payload = extract_json(response_text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"unparseable model response: {exc}") from exc

    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        raise ValueError("model response has no 'findings' list")

    corpus = build_evidence_corpus(diff_text)

    for raw in raw_findings:
        if not isinstance(raw, dict):
            result.rejected_malformed += 1
            continue

        evidence = raw.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            result.rejected_ungrounded += 1
            continue

        # The core anti-hallucination check: the quoted evidence must appear
        # in the diff the model was actually given.
        normalized_evidence = _normalize(evidence.lstrip("+- "))
        if len(normalized_evidence) < 8 or normalized_evidence not in corpus:
            result.rejected_ungrounded += 1
            logger.debug("dropped ungrounded AI finding: %r", evidence[:80])
            continue

        try:
            finding = _build_finding(raw, evidence)
        except (ValueError, KeyError, TypeError):
            result.rejected_malformed += 1
            continue
        result.findings.append(finding)

    return result


def _build_finding(raw: dict, evidence: str) -> Finding:
    severity = Severity(str(raw["severity"]).strip().upper())

    confidence = float(raw.get("confidence", 0.5))
    confidence = min(1.0, max(0.0, confidence))

    sub_category = str(raw.get("category", "correctness")).strip().lower()
    if sub_category not in _KNOWN_CATEGORIES:
        sub_category = "correctness"

    line = raw.get("line")
    line = int(line) if isinstance(line, (int, float)) and int(line) > 0 else None

    title = str(raw.get("title") or "").strip() or None
    explanation = str(raw.get("explanation") or "").strip()
    recommendation = str(raw.get("recommendation") or "").strip()
    if not explanation or not recommendation:
        raise ValueError("finding missing explanation or recommendation")

    return Finding(
        category=Category.AI,
        severity=severity,
        confidence=round(confidence, 2),
        file=str(raw["file"]).strip() if raw.get("file") else None,
        line=line,
        rule=f"AI_{sub_category.upper()}",
        title=title,
        reason=explanation,
        recommendation=recommendation,
        evidence=evidence.strip()[:300],
        source=FindingSource.AI,
    )
