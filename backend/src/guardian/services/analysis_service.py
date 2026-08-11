"""End-to-end analysis pipeline: features → analyzers → AI → scoring → report.

A failure in a single analyzer — including the AI analyzer — is recorded and
skipped: one broken rule or one Bedrock outage must not take down the whole
analysis. When AI does not contribute (disabled, failed, or gated), its
scoring weight is renormalized away so the score stays comparable.
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
from guardian.bedrock.provider import LLMProvider
from guardian.models.config import GuardianConfig
from guardian.models.findings import Finding
from guardian.models.pr import PRContext
from guardian.models.report import AIUsage, AnalyzerFailure, RiskReport
from guardian.scoring.engine import RiskScoringEngine
from guardian.services.feature_extractor import extract_features

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class AnalysisService:
    def __init__(
        self,
        config: GuardianConfig | None = None,
        analyzers: Sequence[BaseAnalyzer] | None = None,
        ai_provider: LLMProvider | None = None,
    ) -> None:
        self.config = config or GuardianConfig()
        self.analyzers: list[BaseAnalyzer] = (
            list(analyzers)
            if analyzers is not None
            else [cls(self.config) for cls in DEFAULT_ANALYZERS]
        )
        # AI runs only when explicitly given a provider AND enabled in config.
        # The CLI/local path stays deterministic-only unless wired up.
        self.ai_provider = ai_provider if (self.config.ai_enabled and ai_provider) else None
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

        ai_usage: AIUsage | None = None
        ai_contributed = False
        if self.ai_provider is not None:
            ai_usage, ai_findings, ai_failure = self._run_ai_stage(pr, features, findings)
            findings.extend(ai_findings)
            ai_contributed = ai_usage.ran
            if ai_failure is not None:
                failures.append(ai_failure)

        findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity.value], -f.confidence))
        result = self.scoring_engine.score(findings, ai_enabled=ai_contributed)

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
            ai=ai_usage,
            duration_ms=round((time.monotonic() - started) * 1000),
        )

    def _run_ai_stage(
        self,
        pr: PRContext,
        features,
        deterministic_findings: list[Finding],
    ) -> tuple[AIUsage, list[Finding], AnalyzerFailure | None]:
        usage = AIUsage(model_id=self.config.bedrock_model_id)

        if self.config.ai_escalation_gate:
            skip_reason = self._gate_skip_reason(deterministic_findings, features)
            if skip_reason:
                usage.skipped_by_gate = True
                usage.skip_reason = skip_reason
                logger.info("AI analysis skipped by escalation gate: %s", skip_reason)
                return usage, [], None

        from guardian.bedrock.analyzer import AIAnalyzer

        analyzer = AIAnalyzer(
            self.config,
            provider=self.ai_provider,
            deterministic_findings=deterministic_findings,
        )
        try:
            ai_findings = analyzer.analyze(pr, features)
        except Exception as exc:  # noqa: BLE001 — Bedrock outage is non-fatal
            logger.exception("AI analyzer failed")
            return usage, [], AnalyzerFailure(analyzer=analyzer.name, error=f"{type(exc).__name__}: {exc}")

        usage.ran = True
        usage.findings_rejected_ungrounded = analyzer.last_rejected_ungrounded
        usage.findings_rejected_malformed = analyzer.last_rejected_malformed
        response = analyzer.last_response
        if response is not None:
            usage.input_tokens = response.input_tokens
            usage.output_tokens = response.output_tokens
            usage.cache_read_tokens = response.cache_read_tokens
            usage.cache_write_tokens = response.cache_write_tokens
            usage.latency_ms = response.latency_ms
            usage.estimated_cost_usd = response.estimated_cost_usd(
                self.config.ai_price_per_mtok_input,
                self.config.ai_price_per_mtok_output,
                self.config.ai_price_per_mtok_cache_read,
            )
        return usage, ai_findings, None

    def _gate_skip_reason(self, findings: list[Finding], features) -> str:
        """Non-empty string = skip AI. Only clearly-low-risk PRs are gated."""
        if features.critical_modules_changed:
            return ""
        if features.total_churn > self.config.ai_gate_max_churn:
            return ""
        deterministic = self.scoring_engine.score(findings, ai_enabled=False)
        if deterministic.overall_risk > self.config.ai_gate_max_deterministic_score:
            return ""
        return (
            f"deterministic risk {deterministic.overall_risk} <= "
            f"{self.config.ai_gate_max_deterministic_score}, churn "
            f"{features.total_churn} <= {self.config.ai_gate_max_churn}, "
            "no critical modules"
        )
