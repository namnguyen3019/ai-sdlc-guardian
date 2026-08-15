"""CloudWatch metrics — deliberately low-cardinality.

Every unique dimension combination bills as a separate custom metric
($0.30/month each), so operational metrics here carry either no dimensions or
the four-value Severity dimension only. Per-repository product analytics
(risk trends, findings per repo) live in DynamoDB where querying them is
effectively free — do not add a Repository dimension to these metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from guardian.models.config import GuardianConfig
from guardian.models.report import RiskReport

logger = logging.getLogger(__name__)


class MetricsPublisher:
    def __init__(self, config: GuardianConfig | None = None, cloudwatch_client: Any | None = None) -> None:
        self.config = config or GuardianConfig()
        self._cloudwatch = cloudwatch_client

    @property
    def cloudwatch(self):
        if self._cloudwatch is None:
            import boto3

            self._cloudwatch = boto3.client("cloudwatch")
        return self._cloudwatch

    def publish_report(self, report: RiskReport) -> None:
        """Best-effort: metrics failures must never fail an analysis."""
        data: list[dict] = [
            {"MetricName": "AnalysisCompleted", "Value": 1, "Unit": "Count"},
            {"MetricName": "AnalysisDuration", "Value": report.duration_ms, "Unit": "Milliseconds"},
            {"MetricName": "OverallRisk", "Value": report.overall_risk, "Unit": "None"},
            {"MetricName": "FindingsTotal", "Value": len(report.findings), "Unit": "Count"},
        ]
        if report.analyzer_failures:
            data.append(
                {"MetricName": "AnalyzerFailures", "Value": len(report.analyzer_failures), "Unit": "Count"}
            )

        severity_counts: dict[str, int] = {}
        for finding in report.findings:
            severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1
        for severity, count in severity_counts.items():
            data.append(
                {
                    "MetricName": "FindingsBySeverity",
                    "Value": count,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Severity", "Value": severity}],
                }
            )

        if report.ai is not None and report.ai.ran:
            data += [
                {"MetricName": "BedrockLatency", "Value": report.ai.latency_ms, "Unit": "Milliseconds"},
                {"MetricName": "BedrockInputTokens", "Value": report.ai.input_tokens, "Unit": "Count"},
                {"MetricName": "BedrockOutputTokens", "Value": report.ai.output_tokens, "Unit": "Count"},
                {"MetricName": "BedrockCacheReadTokens", "Value": report.ai.cache_read_tokens, "Unit": "Count"},
                {"MetricName": "EstimatedAICostUSD", "Value": report.ai.estimated_cost_usd, "Unit": "None"},
                {
                    "MetricName": "AIFindingsRejected",
                    "Value": report.ai.findings_rejected_ungrounded + report.ai.findings_rejected_malformed,
                    "Unit": "Count",
                },
            ]
        if report.ai is not None and report.ai.skipped_by_gate:
            data.append({"MetricName": "AISkippedByGate", "Value": 1, "Unit": "Count"})

        self._put(data)

    def publish_failure(self) -> None:
        self._put([{"MetricName": "AnalysisFailed", "Value": 1, "Unit": "Count"}])

    def publish_count(self, metric_name: str, value: int = 1) -> None:
        """One-off counter (webhook events, comment publishes, …)."""
        self._put([{"MetricName": metric_name, "Value": value, "Unit": "Count"}])

    def _put(self, data: list[dict]) -> None:
        try:
            # PutMetricData accepts at most 1000 datums; ours is far below.
            self.cloudwatch.put_metric_data(Namespace=self.config.metrics_namespace, MetricData=data)
        except Exception:  # noqa: BLE001 — observability must not break analysis
            logger.exception("failed to publish CloudWatch metrics")
