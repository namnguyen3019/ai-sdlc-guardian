"""Step Functions task 1: run the full analysis on a supplied diff.

Input event (either ``diff`` inline or ``diff_s3_key`` in the reports
bucket):

    {
      "repository": "acme/shop",
      "pr_number": 42,
      "base_sha": "...", "head_sha": "...",
      "diff": "diff --git ...",          # or
      "diff_s3_key": "artifacts/....diff"
    }

Output: the full RiskReport as a dict (consumed by the store task). Logs
carry metadata only — never diff content or findings text, per the
no-source-in-logs rule.
"""

from __future__ import annotations

import logging

from guardian.bedrock.client import BedrockProvider
from guardian.github.diff_parser import parse_diff
from guardian.models.env import config_from_env
from guardian.models.pr import PRContext
from guardian.services.analysis_service import AnalysisService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _load_diff(event: dict, config) -> str:
    if event.get("diff"):
        return str(event["diff"])
    key = event.get("diff_s3_key")
    if not key:
        raise ValueError("event must contain 'diff' or 'diff_s3_key'")
    import boto3

    obj = boto3.client("s3").get_object(Bucket=config.reports_bucket, Key=str(key))
    return obj["Body"].read().decode("utf-8", errors="replace")


def handler(event: dict, context: object = None) -> dict:
    config = config_from_env()
    diff_text = _load_diff(event, config)

    pr = PRContext(
        repository=str(event.get("repository", "unknown/unknown")),
        pr_number=int(event.get("pr_number", 0)),
        base_sha=str(event.get("base_sha", "")),
        head_sha=str(event.get("head_sha", "")),
        files=parse_diff(diff_text),
    )
    logger.info(
        "analyzing %s#%s: %d files, +%d/-%d",
        pr.repository, pr.pr_number, len(pr.files), pr.total_additions, pr.total_deletions,
    )

    provider = BedrockProvider(config) if config.ai_enabled else None
    report = AnalysisService(config, ai_provider=provider).analyze(pr)

    logger.info(
        "analysis %s: risk=%d level=%s ai_ran=%s failures=%d",
        report.analysis_id, report.overall_risk, report.risk_level.value,
        bool(report.ai and report.ai.ran), len(report.analyzer_failures),
    )
    return report.model_dump(mode="json")
