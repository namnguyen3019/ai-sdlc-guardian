"""Step Functions task 2: persist the report and publish metrics.

Input: the RiskReport dict produced by the analyze task.
Output: a compact summary (kept small for Step Functions payload limits and
for the Week 3 GitHub-comment task).
"""

from __future__ import annotations

import logging

from guardian.models.env import config_from_env
from guardian.models.report import RiskReport
from guardian.services.metrics import MetricsPublisher
from guardian.services.storage import AnalysisStore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: object = None) -> dict:
    config = config_from_env()
    report = RiskReport.model_validate(event)

    key = AnalysisStore(config).save(report)
    MetricsPublisher(config).publish_report(report)

    return {
        "analysis_id": report.analysis_id,
        "repository": report.repository,
        "pr_number": report.pr_number,
        "overall_risk": report.overall_risk,
        "risk_level": report.risk_level.value,
        "merge_recommendation": report.merge_recommendation.value,
        "report_s3_key": key,
    }
