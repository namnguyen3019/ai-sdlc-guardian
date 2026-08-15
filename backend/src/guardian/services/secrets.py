"""GitHub credentials from AWS Secrets Manager, cached per Lambda container.

The secret is a JSON object: {"token": "...", "webhook_secret": "..."}.
Values never appear in logs or reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from guardian.models.config import GuardianConfig

_cache: dict[str, "GitHubSecrets"] = {}


@dataclass(frozen=True)
class GitHubSecrets:
    token: str
    webhook_secret: str


def clear_cache() -> None:
    _cache.clear()


def get_github_secrets(config: GuardianConfig, client: Any | None = None) -> GitHubSecrets:
    arn = config.github_secret_arn
    if not arn:
        raise ValueError("github_secret_arn is not configured")
    if arn in _cache:
        return _cache[arn]

    if client is None:
        import boto3

        client = boto3.client("secretsmanager")

    import json

    raw = client.get_secret_value(SecretId=arn)["SecretString"]
    data = json.loads(raw)
    secrets = GitHubSecrets(
        token=str(data.get("token", "")),
        webhook_secret=str(data.get("webhook_secret", "")),
    )
    _cache[arn] = secrets
    return secrets
