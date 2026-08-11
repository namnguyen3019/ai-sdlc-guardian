"""Risk report models — the final, explainable output of an analysis."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from guardian.models.features import PRFeatures
from guardian.models.findings import Finding


class RiskLevel(str, Enum):
    LOW = "LOW"            # 0-30
    MEDIUM = "MEDIUM"      # 31-60
    HIGH = "HIGH"          # 61-80
    CRITICAL = "CRITICAL"  # 81-100

    @property
    def rank(self) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[self.value]

    @classmethod
    def from_score(cls, score: int) -> "RiskLevel":
        if score <= 30:
            return cls.LOW
        if score <= 60:
            return cls.MEDIUM
        if score <= 80:
            return cls.HIGH
        return cls.CRITICAL


class MergeRecommendation(str, Enum):
    APPROVE = "APPROVE"
    REVIEW_RECOMMENDED = "REVIEW RECOMMENDED"
    REVIEW_REQUIRED = "REVIEW REQUIRED"
    BLOCK = "BLOCK"


class CategoryScores(BaseModel):
    """Per-dimension scores, each 0-100."""

    security: int = 0
    testing: int = 0
    change_impact: int = 0
    complexity: int = 0
    ai_risk: int = 0


class ScoreExplanation(BaseModel):
    """Why a scoring dimension received its score."""

    dimension: str
    score: int
    weight: float
    weighted_contribution: float
    detail: str


class AnalyzerFailure(BaseModel):
    analyzer: str
    error: str


class RiskReport(BaseModel):
    """Complete result of one pull-request analysis."""

    analysis_id: str
    timestamp: datetime
    engine_version: str
    repository: str
    pr_number: int
    base_sha: str = ""
    head_sha: str = ""

    overall_risk: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    merge_recommendation: MergeRecommendation
    scores: CategoryScores
    weights_used: dict[str, float] = Field(default_factory=dict)
    explanations: list[ScoreExplanation] = Field(default_factory=list)

    findings: list[Finding] = Field(default_factory=list)
    features: PRFeatures
    analyzer_failures: list[AnalyzerFailure] = Field(default_factory=list)
    duration_ms: int = 0
