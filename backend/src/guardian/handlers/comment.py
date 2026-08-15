"""Step Functions task 3: publish the risk report as a GitHub PR comment.

The comment carries a hidden marker; on subsequent pushes the existing
comment is updated in place instead of posting a duplicate.
"""

from __future__ import annotations

import logging
from typing import Any

from guardian.github.client import GitHubClient
from guardian.models.env import config_from_env
from guardian.models.report import RiskReport
from guardian.reporting.markdown import GUARDIAN_COMMENT_MARKER, render_markdown
from guardian.services.metrics import MetricsPublisher
from guardian.services.secrets import get_github_secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_TRUNCATION_NOTE = "\n\n---\n*Report truncated for GitHub's comment size limit; the full report is stored in S3.*"


def _comment_body(report: RiskReport, max_chars: int) -> str:
    body = render_markdown(report)
    if len(body) > max_chars:
        body = body[:max_chars] + _TRUNCATION_NOTE
    return body


def handler(event: dict, context: object = None, *, github_client: GitHubClient | None = None,
            s3_client: Any = None, secrets_client: Any = None) -> dict:
    config = config_from_env()
    repository = str(event["repository"])
    pr_number = int(event["pr_number"])
    report_s3_key = str(event["report_s3_key"])

    if s3_client is None:
        import boto3

        s3_client = boto3.client("s3")
    raw = s3_client.get_object(Bucket=config.reports_bucket, Key=report_s3_key)["Body"].read()
    report = RiskReport.model_validate_json(raw)

    if github_client is None:
        secrets = get_github_secrets(config, client=secrets_client)
        github_client = GitHubClient(secrets.token, config.github_api_url)

    body = _comment_body(report, config.comment_max_chars)
    comment_id, action = github_client.upsert_marked_comment(
        repository, pr_number, body, GUARDIAN_COMMENT_MARKER
    )

    MetricsPublisher(config).publish_count("CommentPublished")
    logger.info("comment %s on %s#%d (id %d)", action, repository, pr_number, comment_id)
    return {**event, "comment_id": comment_id, "comment_action": action}
