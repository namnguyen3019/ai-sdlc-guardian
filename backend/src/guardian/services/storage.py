"""Persistence: analysis metadata in DynamoDB, full reports in S3.

Data-minimization rules (see SECURITY.md):

* DynamoDB stores metadata only — scores, status, timings, cost. Never
  findings text, never diff content.
* S3 stores the full report. Reports contain finding evidence (diff excerpts
  of at most 300 characters each) because explainability requires pointing at
  the offending line; they never contain whole files or the full diff.
"""

from __future__ import annotations

import logging
from typing import Any

from guardian.models.config import GuardianConfig
from guardian.models.report import RiskReport

logger = logging.getLogger(__name__)


def _pk(repository: str, pr_number: int) -> str:
    return f"REPO#{repository}#PR#{pr_number}"


def _sk(report: RiskReport) -> str:
    return f"TS#{report.timestamp.isoformat()}#{report.analysis_id}"


def report_s3_key(report: RiskReport) -> str:
    return f"reports/{report.repository}/{report.pr_number}/{report.analysis_id}.json"


class AnalysisStore:
    def __init__(
        self,
        config: GuardianConfig | None = None,
        dynamodb_resource: Any | None = None,
        s3_client: Any | None = None,
    ) -> None:
        self.config = config or GuardianConfig()
        self._dynamodb = dynamodb_resource
        self._s3 = s3_client

    @property
    def table(self):
        if self._dynamodb is None:
            import boto3

            self._dynamodb = boto3.resource("dynamodb")
        return self._dynamodb.Table(self.config.dynamodb_table)

    @property
    def s3(self):
        if self._s3 is None:
            import boto3

            self._s3 = boto3.client("s3")
        return self._s3

    def save(self, report: RiskReport) -> str:
        """Persist the report; returns the S3 key of the full report."""
        key = report_s3_key(report)
        self.s3.put_object(
            Bucket=self.config.reports_bucket,
            Key=key,
            Body=report.model_dump_json(indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        self.table.put_item(Item=self._metadata_item(report, key))
        logger.info("stored analysis %s at s3://%s/%s", report.analysis_id, self.config.reports_bucket, key)
        return key

    def get_recent(self, repository: str, limit: int = 25) -> list[dict]:
        """Most recent analyses for a repository (dashboard access pattern)."""
        response = self.table.query(
            IndexName="byRepository",
            KeyConditionExpression="repository = :r",
            ExpressionAttributeValues={":r": repository},
            ScanIndexForward=False,
            Limit=limit,
        )
        return response.get("Items", [])

    def _metadata_item(self, report: RiskReport, key: str) -> dict:
        severity_counts: dict[str, int] = {}
        for finding in report.findings:
            severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1
        item = {
            "pk": _pk(report.repository, report.pr_number),
            "sk": _sk(report),
            "analysis_id": report.analysis_id,
            "repository": report.repository,
            "pr_number": report.pr_number,
            "timestamp": report.timestamp.isoformat(),
            "base_sha": report.base_sha,
            "head_sha": report.head_sha,
            "status": "FAILED_PARTIAL" if report.analyzer_failures else "COMPLETED",
            "overall_risk": report.overall_risk,
            "risk_level": report.risk_level.value,
            "merge_recommendation": report.merge_recommendation.value,
            "score_security": report.scores.security,
            "score_testing": report.scores.testing,
            "score_change_impact": report.scores.change_impact,
            "score_complexity": report.scores.complexity,
            "score_ai_risk": report.scores.ai_risk,
            "findings_total": len(report.findings),
            "findings_by_severity": severity_counts,
            "engine_version": report.engine_version,
            "duration_ms": report.duration_ms,
            "report_s3_key": key,
        }
        if report.ai is not None:
            item.update(
                {
                    "model_id": report.ai.model_id,
                    "ai_ran": report.ai.ran,
                    "ai_skipped_by_gate": report.ai.skipped_by_gate,
                    "ai_input_tokens": report.ai.input_tokens,
                    "ai_output_tokens": report.ai.output_tokens,
                    "ai_latency_ms": report.ai.latency_ms,
                    # DynamoDB rejects float; store micro-USD as an integer.
                    "ai_cost_micro_usd": int(report.ai.estimated_cost_usd * 1_000_000),
                }
            )
        return item
