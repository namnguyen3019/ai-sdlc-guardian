import hashlib
import hmac
import json

import boto3
import pytest
from moto import mock_aws

from guardian.handlers import webhook as webhook_handler
from guardian.services import secrets

TABLE = "guardian-webhook-analyses"
WEBHOOK_SECRET = "whsec-testing"

SFN_DEFINITION = json.dumps({"StartAt": "Done", "States": {"Done": {"Type": "Pass", "End": True}}})


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def pr_body(action="opened", number=42) -> bytes:
    return json.dumps(
        {
            "action": action,
            "pull_request": {"number": number, "base": {"sha": "b1"}, "head": {"sha": "h1"}},
            "repository": {"full_name": "acme/shop"},
        }
    ).encode()


def url_event(body: bytes, signature: str | None, event_name="pull_request", delivery="dlv-1") -> dict:
    headers = {"x-github-event": event_name, "x-github-delivery": delivery, "content-type": "application/json"}
    if signature is not None:
        headers["x-hub-signature-256"] = signature
    return {"headers": headers, "body": body.decode(), "isBase64Encoded": False}


@pytest.fixture
def webhook_env(monkeypatch):
    secrets.clear_cache()
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("GUARDIAN_TABLE", TABLE)
    with mock_aws():
        secret_arn = boto3.client("secretsmanager").create_secret(
            Name="guardian/github",
            SecretString=json.dumps({"token": "tok", "webhook_secret": WEBHOOK_SECRET}),
        )["ARN"]
        monkeypatch.setenv("GUARDIAN_GITHUB_SECRET_ARN", secret_arn)

        boto3.resource("dynamodb").create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        sfn = boto3.client("stepfunctions")
        machine_arn = sfn.create_state_machine(
            name="guardian-test",
            definition=SFN_DEFINITION,
            roleArn="arn:aws:iam::123456789012:role/sfn-test-role",
        )["stateMachineArn"]
        monkeypatch.setenv("GUARDIAN_STATE_MACHINE_ARN", machine_arn)
        yield {"sfn": sfn, "machine_arn": machine_arn}
    secrets.clear_cache()


def executions(env) -> list[dict]:
    return env["sfn"].list_executions(stateMachineArn=env["machine_arn"])["executions"]


def test_valid_pr_event_starts_execution(webhook_env):
    body = pr_body()
    response = webhook_handler.handler(url_event(body, sign(body)))
    assert response["statusCode"] == 202
    runs = executions(webhook_env)
    assert len(runs) == 1
    described = webhook_env["sfn"].describe_execution(executionArn=runs[0]["executionArn"])
    launch_input = json.loads(described["input"])
    assert launch_input["repository"] == "acme/shop"
    assert launch_input["pr_number"] == 42
    assert launch_input["head_sha"] == "h1"


def test_invalid_signature_is_401_and_starts_nothing(webhook_env):
    body = pr_body()
    bad = "sha256=" + hmac.new(b"wrong", body, hashlib.sha256).hexdigest()
    assert webhook_handler.handler(url_event(body, bad))["statusCode"] == 401
    assert webhook_handler.handler(url_event(body, None))["statusCode"] == 401
    assert executions(webhook_env) == []


def test_ping_and_ignored_events(webhook_env):
    ping = json.dumps({"zen": "Design for failure."}).encode()
    assert webhook_handler.handler(url_event(ping, sign(ping), event_name="ping"))["statusCode"] == 200

    closed = pr_body(action="closed")
    response = webhook_handler.handler(url_event(closed, sign(closed), delivery="dlv-2"))
    assert response["statusCode"] == 200
    assert executions(webhook_env) == []


def test_duplicate_delivery_analyzed_once(webhook_env):
    body = pr_body()
    first = webhook_handler.handler(url_event(body, sign(body), delivery="same-id"))
    second = webhook_handler.handler(url_event(body, sign(body), delivery="same-id"))
    assert first["statusCode"] == 202
    assert second["statusCode"] == 200
    assert "duplicate" in json.loads(second["body"])["message"]
    assert len(executions(webhook_env)) == 1


def test_distinct_deliveries_both_analyzed(webhook_env):
    body = pr_body()
    webhook_handler.handler(url_event(body, sign(body), delivery="d-a"))
    webhook_handler.handler(url_event(body, sign(body), delivery="d-b"))
    assert len(executions(webhook_env)) == 2
