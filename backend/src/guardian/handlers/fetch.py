"""Step Functions task 0: fetch PR metadata and diff from GitHub.

Uploads the diff to ``artifacts/`` (90-day expiry) and passes only its S3 key
downstream — diffs can exceed the Step Functions payload limit.
"""

from __future__ import annotations

import logging
from typing import Any

from guardian.github.client import GitHubClient
from guardian.models.env import config_from_env
from guardian.services.secrets import get_github_secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: object = None, *, github_client: GitHubClient | None = None,
            s3_client: Any = None, secrets_client: Any = None) -> dict:
    config = config_from_env()
    repository = str(event["repository"])
    pr_number = int(event["pr_number"])

    if github_client is None:
        secrets = get_github_secrets(config, client=secrets_client)
        github_client = GitHubClient(secrets.token, config.github_api_url)

    pr_meta = github_client.get_pr(repository, pr_number)
    diff_text = github_client.get_pr_diff(repository, pr_number)

    head_sha = str((pr_meta.get("head") or {}).get("sha") or event.get("head_sha") or "unknown")
    base_sha = str((pr_meta.get("base") or {}).get("sha") or event.get("base_sha") or "")
    diff_s3_key = f"artifacts/{repository}/{pr_number}/{head_sha}.diff"

    if s3_client is None:
        import boto3

        s3_client = boto3.client("s3")
    s3_client.put_object(
        Bucket=config.reports_bucket,
        Key=diff_s3_key,
        Body=diff_text.encode("utf-8"),
        ContentType="text/x-diff",
    )
    logger.info("fetched %s#%d: %d-char diff at %s", repository, pr_number, len(diff_text), diff_s3_key)

    return {
        "repository": repository,
        "pr_number": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "delivery_id": str(event.get("delivery_id", "")),
        "diff_s3_key": diff_s3_key,
    }
