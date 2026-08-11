import boto3
import pytest
from moto import mock_aws

from guardian.handlers import analyze as analyze_handler
from guardian.handlers import store as store_handler

TABLE = "guardian-handler-analyses"
BUCKET = "guardian-handler-reports"


@pytest.fixture
def lambda_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("GUARDIAN_TABLE", TABLE)
    monkeypatch.setenv("GUARDIAN_BUCKET", BUCKET)
    monkeypatch.setenv("GUARDIAN_AI_ENABLED", "false")  # no Bedrock in tests
    with mock_aws():
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
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        yield


def test_analyze_then_store_roundtrip(lambda_env, fixtures_dir):
    diff_text = (fixtures_dir / "risky_payment.diff").read_text()
    event = {
        "repository": "acme/shop",
        "pr_number": 42,
        "base_sha": "abc1234",
        "head_sha": "def5678",
        "diff": diff_text,
    }

    report_dict = analyze_handler.handler(event)
    assert report_dict["repository"] == "acme/shop"
    assert report_dict["overall_risk"] > 50
    assert report_dict["ai"] is None  # AI disabled via env

    summary = store_handler.handler(report_dict)
    assert summary["analysis_id"] == report_dict["analysis_id"]
    assert summary["risk_level"] == report_dict["risk_level"]

    stored = boto3.client("s3").get_object(Bucket=BUCKET, Key=summary["report_s3_key"])
    assert report_dict["analysis_id"] in stored["Body"].read().decode()


def test_analyze_reads_diff_from_s3(lambda_env, fixtures_dir):
    diff_text = (fixtures_dir / "safe_docs.diff").read_text()
    boto3.client("s3").put_object(Bucket=BUCKET, Key="artifacts/pr-7.diff", Body=diff_text.encode())

    report_dict = analyze_handler.handler(
        {"repository": "acme/shop", "pr_number": 7, "diff_s3_key": "artifacts/pr-7.diff"}
    )
    assert report_dict["risk_level"] == "LOW"


def test_analyze_rejects_missing_diff(lambda_env):
    with pytest.raises(ValueError):
        analyze_handler.handler({"repository": "acme/shop", "pr_number": 1})
