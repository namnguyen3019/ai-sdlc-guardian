"""Explainable 0-100 risk scoring.

Design rules:

* The score is computed *only* by this engine from structured findings.
  The LLM never outputs the final score — its findings are just one more
  signal, mapped into the ``ai_risk`` dimension.
* Each dimension score is a confidence-weighted sum of severity points,
  capped at 100 — simple enough that every score can be traced back to the
  findings that produced it.
* Dimension weights are configurable; weights of dimensions that produced no
  signal *source* (e.g. AI analysis disabled) are renormalized away rather
  than silently deflating the overall score.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from guardian.models.config import GuardianConfig
from guardian.models.findings import Category, Finding, Severity
from guardian.models.report import (
    CategoryScores,
    MergeRecommendation,
    RiskLevel,
    ScoreExplanation,
)

# findings category → scoring dimension
CATEGORY_TO_DIMENSION: dict[Category, str] = {
    Category.SECURITY: "security",
    Category.TESTING: "testing",
    Category.CHANGE_IMPACT: "change_impact",
    Category.DEPENDENCY: "change_impact",
    Category.COMPLEXITY: "complexity",
    Category.AI: "ai_risk",
}

DIMENSIONS = ("security", "testing", "change_impact", "complexity", "ai_risk")


class ScoringResult(BaseModel):
    overall_risk: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    merge_recommendation: MergeRecommendation
    scores: CategoryScores
    weights_used: dict[str, float]
    explanations: list[ScoreExplanation]


class RiskScoringEngine:
    def __init__(self, config: GuardianConfig | None = None) -> None:
        self.config = config or GuardianConfig()

    def score(self, findings: list[Finding], ai_enabled: bool = False) -> ScoringResult:
        by_dimension: dict[str, list[Finding]] = {d: [] for d in DIMENSIONS}
        for finding in findings:
            by_dimension[CATEGORY_TO_DIMENSION[finding.category]].append(finding)

        dim_scores = {d: self._dimension_score(fs) for d, fs in by_dimension.items()}
        weights = self._effective_weights(ai_enabled)
        overall = round(sum(weights[d] * dim_scores[d] for d in weights))
        overall = max(0, min(100, overall))
        level = RiskLevel.from_score(overall)

        explanations = [
            ScoreExplanation(
                dimension=d,
                score=dim_scores[d],
                weight=round(weights.get(d, 0.0), 4),
                weighted_contribution=round(weights.get(d, 0.0) * dim_scores[d], 1),
                detail=self._explain_dimension(d, by_dimension[d], ai_enabled),
            )
            for d in DIMENSIONS
        ]

        return ScoringResult(
            overall_risk=overall,
            risk_level=level,
            merge_recommendation=self._recommendation(level),
            scores=CategoryScores(**dim_scores),
            weights_used={k: round(v, 4) for k, v in weights.items()},
            explanations=explanations,
        )

    def _dimension_score(self, findings: list[Finding]) -> int:
        points = self.config.severity_points
        total = sum(points[f.severity.value] * f.confidence for f in findings)
        return min(100, round(total))

    def _effective_weights(self, ai_enabled: bool) -> dict[str, float]:
        raw = self.config.weights.model_dump()
        if not ai_enabled:
            raw.pop("ai_risk")
        total = sum(raw.values())
        if total <= 0:
            # All weight sat on unavailable dimensions (e.g. an LLM-only
            # configuration with AI down) — no signal, score 0, not a crash.
            return {}
        return {k: v / total for k, v in raw.items()}

    @staticmethod
    def _recommendation(level: RiskLevel) -> MergeRecommendation:
        return {
            RiskLevel.LOW: MergeRecommendation.APPROVE,
            RiskLevel.MEDIUM: MergeRecommendation.REVIEW_RECOMMENDED,
            RiskLevel.HIGH: MergeRecommendation.REVIEW_REQUIRED,
            RiskLevel.CRITICAL: MergeRecommendation.BLOCK,
        }[level]

    @staticmethod
    def _explain_dimension(dimension: str, findings: list[Finding], ai_enabled: bool) -> str:
        if dimension == "ai_risk" and not ai_enabled:
            return "AI analysis was not run; its weight was redistributed."
        if not findings:
            return "No findings in this dimension."
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        ordered = [s.value for s in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)]
        summary = ", ".join(f"{counts[s]} {s}" for s in ordered if s in counts)
        top = max(findings, key=lambda f: (f.severity.rank, f.confidence))
        where = f" in {top.file}" + (f":{top.line}" if top.line else "") if top.file else ""
        return f"{summary} finding(s); most severe: {top.rule}{where}."
