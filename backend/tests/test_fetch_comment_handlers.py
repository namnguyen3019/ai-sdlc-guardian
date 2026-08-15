import boto3
import pytest
from moto import mock_aws

from guardian.handlers import comment as comment_handler
from guardian.handlers import fetch as fetch_handler
from guardian.github.pr_loader import load_pr
from guardian.reporting.markdown import GUARDIAN_COMMENT_MARKER
from guardian.services.analysis_service import AnalysisService
from guardian.services.storage import report_s3_key
from guardian.models.config import GuardianConfig

BUCKET = "guardian-gh-reports"


class StubGitHub:
    """In-memory GitHubClient double for handler tests."""

    def __init__(self, diff_text=""):
        self.diff_text = diff_text
        self.comments: list[dict] = []
        self._next_id = 1

    def get_pr(self, repository, pr_number):
        return {"number": pr_number, "head": {"sha": "headsha"}, "base": {"sha": "basesha"}}

    def get_pr_diff(self, repository, pr_number):
        return self.diff_text

    def upsert_marked_comment(self, repository, pr_number, body, marker):
        for existing in self.comments:
            if marker in existing["body"]:
                existing["body"] = body
                return existing["id"], "updated"
        self._next_id += 1
        self.comments.append({"id": self._next_id, "body": body})
        return self._next_id, "created"


@pytest.fixture
def gh_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("GUARDIAN_BUCKET", BUCKET)
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        yield


def test_fetch_uploads_diff_and_returns_key(gh_env, fixtures_dir):
    diff_text = (fixtures_dir / "risky_payment.diff").read_text()
    stub = StubGitHub(diff_text)
    result = fetch_handler.handler(
        {"repository": "acme/shop", "pr_number": 42, "delivery_id": "d-1"},
        github_client=stub,
    )
    assert result["diff_s3_key"] == "artifacts/acme/shop/42/headsha.diff"
    assert result["head_sha"] == "headsha"
    stored = boto3.client("s3").get_object(Bucket=BUCKET, Key=result["diff_s3_key"])
    assert stored["Body"].read().decode() == diff_text


def store_report(fixtures_dir) -> dict:
    pr = load_pr(fixtures_dir / "risky_payment.diff", fixtures_dir / "meta.json")
    report = AnalysisService().analyze(pr)
    key = report_s3_key(report)
    boto3.client("s3").put_object(Bucket=BUCKET, Key=key, Body=report.model_dump_json().encode())
    return {"repository": "acme/shop", "pr_number": 42, "report_s3_key": key}


def test_comment_created_then_updated_in_place(gh_env, fixtures_dir):
    event = store_report(fixtures_dir)
    stub = StubGitHub()

    first = comment_handler.handler(dict(event), github_client=stub)
    assert first["comment_action"] == "created"
    assert len(stub.comments) == 1
    assert GUARDIAN_COMMENT_MARKER in stub.comments[0]["body"]
    assert "Overall Risk" in stub.comments[0]["body"]

    second = comment_handler.handler(dict(event), github_client=stub)
    assert second["comment_action"] == "updated"
    assert len(stub.comments) == 1  # no duplicate comment on re-run
    assert second["comment_id"] == first["comment_id"]


def test_comment_truncated_to_limit(gh_env, fixtures_dir, monkeypatch):
    event = store_report(fixtures_dir)
    stub = StubGitHub()
    monkeypatch.setattr(comment_handler, "_TRUNCATION_NOTE", "\n[truncated]")
    monkeypatch.setattr(
        comment_handler, "config_from_env",
        lambda: GuardianConfig(reports_bucket=BUCKET, comment_max_chars=500),
    )
    comment_handler.handler(dict(event), github_client=stub)
    body = stub.comments[0]["body"]
    assert body.endswith("[truncated]")
    assert len(body) <= 520
