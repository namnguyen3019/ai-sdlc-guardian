"""Webhook receiver (Lambda Function URL).

Order of operations is security-relevant:

1. Verify the HMAC signature — before parsing the payload at all. The
   signature is the endpoint's authentication; everything failing it is 401.
2. Filter to pull_request opened/reopened/synchronize.
3. De-duplicate on the delivery id (DynamoDB conditional put with TTL) so
   GitHub redeliveries don't double-analyze.
4. Start the Step Functions execution and return 202 immediately — all slow
   work happens in the workflow, keeping the webhook well under GitHub's
   10-second delivery timeout.

Logs carry identifiers only (repo, PR number, delivery id) — never payload
bodies, which contain attacker-controlled text.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from typing import Any

from guardian.github.webhook import parse_pr_event, verify_signature
from guardian.models.env import config_from_env
from guardian.services.metrics import MetricsPublisher
from guardian.services.secrets import get_github_secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_EXECUTION_NAME_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _response(status: int, message: str) -> dict:
    return {"statusCode": status, "body": json.dumps({"message": message})}


def _headers(event: dict) -> dict[str, str]:
    return {k.lower(): v for k, v in (event.get("headers") or {}).items()}


def _body_bytes(event: dict) -> bytes:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return body.encode("utf-8")


def _deduplicate(config, dynamodb: Any, delivery_id: str) -> bool:
    """True if this delivery is new; False if already seen."""
    try:
        dynamodb.Table(config.dynamodb_table).put_item(
            Item={
                "pk": f"DELIVERY#{delivery_id}",
                "sk": "DELIVERY",
                "ttl": int(time.time()) + config.webhook_dedup_ttl_seconds,
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def handler(event: dict, context: object = None, *, sfn_client: Any = None,
            dynamodb_resource: Any = None, secrets_client: Any = None) -> dict:
    config = config_from_env()
    metrics = MetricsPublisher(config)
    headers = _headers(event)
    body = _body_bytes(event)

    secrets = get_github_secrets(config, client=secrets_client)
    if not verify_signature(secrets.webhook_secret, body, headers.get("x-hub-signature-256")):
        metrics.publish_count("WebhookInvalidSignature")
        logger.warning("webhook rejected: bad or missing signature")
        return _response(401, "invalid signature")

    event_name = headers.get("x-github-event", "")
    delivery_id = headers.get("x-github-delivery", "")
    metrics.publish_count("WebhookReceived")

    if event_name == "ping":
        return _response(200, "pong")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _response(400, "malformed payload")

    pr_event = parse_pr_event(event_name, delivery_id, payload)
    if pr_event is None:
        metrics.publish_count("WebhookIgnored")
        return _response(200, "event ignored")

    if dynamodb_resource is None:
        import boto3

        dynamodb_resource = boto3.resource("dynamodb")
    if delivery_id and not _deduplicate(config, dynamodb_resource, delivery_id):
        metrics.publish_count("WebhookDuplicate")
        logger.info("duplicate delivery %s ignored", delivery_id)
        return _response(200, "duplicate delivery")

    if sfn_client is None:
        import boto3

        sfn_client = boto3.client("stepfunctions")

    execution_name = _EXECUTION_NAME_SAFE.sub(
        "-", f"{pr_event.repository}-{pr_event.pr_number}-{delivery_id or pr_event.head_sha}"
    )[:80]
    sfn_client.start_execution(
        stateMachineArn=config.state_machine_arn,
        name=execution_name,
        input=json.dumps(
            {
                "repository": pr_event.repository,
                "pr_number": pr_event.pr_number,
                "action": pr_event.action,
                "base_sha": pr_event.base_sha,
                "head_sha": pr_event.head_sha,
                "delivery_id": delivery_id,
            }
        ),
    )
    logger.info(
        "started analysis for %s#%d (%s, delivery %s)",
        pr_event.repository, pr_event.pr_number, pr_event.action, delivery_id,
    )
    metrics.publish_count("WebhookAccepted")
    return _response(202, "analysis started")
