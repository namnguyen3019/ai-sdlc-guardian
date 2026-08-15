import json

import boto3
import pytest
from moto import mock_aws

from guardian.models.config import GuardianConfig
from guardian.services import secrets


@pytest.fixture(autouse=True)
def clear_secret_cache():
    secrets.clear_cache()
    yield
    secrets.clear_cache()


@pytest.fixture
def secret_arn(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = boto3.client("secretsmanager")
        response = client.create_secret(
            Name="guardian/github",
            SecretString=json.dumps({"token": "gh-token", "webhook_secret": "whsec"}),
        )
        yield response["ARN"]


def test_secrets_fetched_and_cached(secret_arn):
    config = GuardianConfig(github_secret_arn=secret_arn)

    class CountingClient:
        def __init__(self):
            self.calls = 0
            self._client = boto3.client("secretsmanager")

        def get_secret_value(self, **kwargs):
            self.calls += 1
            return self._client.get_secret_value(**kwargs)

    counting = CountingClient()
    first = secrets.get_github_secrets(config, client=counting)
    second = secrets.get_github_secrets(config, client=counting)
    assert first.token == "gh-token"
    assert first.webhook_secret == "whsec"
    assert second is first
    assert counting.calls == 1


def test_missing_arn_raises():
    with pytest.raises(ValueError):
        secrets.get_github_secrets(GuardianConfig(github_secret_arn=""))
