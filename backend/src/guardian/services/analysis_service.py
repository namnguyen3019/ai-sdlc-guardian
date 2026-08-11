"""End-to-end analysis pipeline: features → analyzers → scoring → report.

A failure in a single analyzer is recorded and skipped — one broken rule must
not take down the whole analysis (mirrors the Step Functions error handling
added in Week 2).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Sequence

import guardian
from guardian.analyzers import DEFAULT_ANALYZERS
from guardian.analyzers.base import BaseAnalyzer
from guardian.models.config import GuardianConfig
from guardian.models.findings import Finding
from guardian.models.pr import PRContext
from guardian.models.report import AnalyzerFailure, RiskReport
from guardian.scoring.engine import RiskScoringEngine
from guardian.services.feature_extractor import extract_features

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class AnalysisService:
    def __init__(
        self,
        config: GuardianConfig | None = None,
        analyzers: Sequence[BaseAnalyzer] | None = None,
    ) -> None:
        self.config = config or GuardianConfig()
        self.analyzers: list[BaseAnalyzer] = (
            list(analyzers)
            if analyzers is not None
            else [cls(self.config) for cls in DEFAULT_ANALYZERS]
        )
        self.scoring_engine = RiskScoringEngine(self.config)

    def analyze(self, pr: PRContext) -> RiskReport:
        started = time.monotonic()
        features = extract_features(pr, self.config)

        findings: list[Finding] = []
        failures: list[AnalyzerFailure] = []
        for analyzer in self.analyzers:
            try:
                findings.extend(analyzer.analyze(pr, features))
            except Exception as exc:  # noqa: BLE001 — isolation is the point
                logger.exception("analyzer %s failed", analyzer.name)
                failures.append(AnalyzerFailure(analyzer=analyzer.name, error=f"{type(exc).__name__}: {exc}"))

        findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity.value], -f.confidence))
        result = self.scoring_engine.score(findings, ai_enabled=False)

        return RiskReport(
            analysis_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engine_version=guardian.__version__,
            repository=pr.repository,
            pr_number=pr.pr_number,
            base_sha=pr.base_sha,
            head_sha=pr.head_sha,
            overall_risk=result.overall_risk,
            risk_level=result.risk_level,
            merge_recommendation=result.merge_recommendation,
            scores=result.scores,
            weights_used=result.weights_used,
            explanations=result.explanations,
            findings=findings,
            features=features,
            analyzer_failures=failures,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
