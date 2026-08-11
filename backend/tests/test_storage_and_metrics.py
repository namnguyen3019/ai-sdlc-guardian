import boto3
import pytest
from moto import mock_aws

from guardian.github.pr_loader import load_pr
from guardian.models.config import GuardianConfig
from guardian.services.analysis_service import AnalysisService
from guardian.services.metrics import MetricsPublisher
from guardian.services.storage import AnalysisStore

TABLE = "guardian-test-analyses"
BUCKET = "guardian-test-reports"


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        dynamodb.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "repository", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "byRepository",
                    "KeySchema": [
                        {"AttributeName": "repository", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        yield


@pytest.fixture
def config():
    return GuardianConfig(dynamodb_table=TABLE, reports_bucket=BUCKET)


def make_report(fixtures_dir):
    pr = load_pr(fixtures_dir / "risky_payment.diff", fixtures_dir / "meta.json")
    return AnalysisService().analyze(pr)


def test_save_writes_metadata_and_report(aws_env, config, fixtures_dir):
    report = make_report(fixtures_dir)
    key = AnalysisStore(config).save(report)

    body = boto3.client("s3").get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()
    assert report.analysis_id in body

    items = boto3.resource("dynamodb").Table(TABLE).query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq("REPO#acme/shop#PR#42")
    )["Items"]
    assert len(items) == 1
    item = items[0]
    assert item["overall_risk"] == report.overall_risk
    assert item["risk_level"] == report.risk_level.value
    assert item["report_s3_key"] == key
    # Metadata only — no findings text, no diff content, in DynamoDB.
    assert "findings" not in item
    assert "SELECT" not in str(item)


def test_get_recent_via_gsi(aws_env, config, fixtures_dir):
    store = AnalysisStore(config)
    report = make_report(fixtures_dir)
    store.save(report)
    recent = store.get_recent("acme/shop")
    assert len(recent) == 1
    assert recent[0]["analysis_id"] == report.analysis_id
    assert store.get_recent("other/repo") == []


def test_metrics_publish(aws_env, config, fixtures_dir):
    report = make_report(fixtures_dir)
    MetricsPublisher(config).publish_report(report)
    MetricsPublisher(config).publish_failure()

    names = {
        m["MetricName"]
        for m in boto3.client("cloudwatch").list_metrics(Namespace=config.metrics_namespace)["Metrics"]
    }
    assert {"AnalysisCompleted", "AnalysisDuration", "OverallRisk", "FindingsBySeverity", "AnalysisFailed"} <= names


def test_metrics_failure_is_swallowed(config, fixtures_dir):
    class BrokenClient:
        def put_metric_data(self, **kwargs):
            raise RuntimeError("cloudwatch down")

    report = make_report(fixtures_dir)
    MetricsPublisher(config, cloudwatch_client=BrokenClient()).publish_report(report)  # must not raise
