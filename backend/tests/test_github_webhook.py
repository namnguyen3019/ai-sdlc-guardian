import hashlib
import hmac

from guardian.github.webhook import parse_pr_event, verify_signature

SECRET = "test-webhook-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def pr_payload(action="opened", number=42):
    return {
        "action": action,
        "pull_request": {
            "number": number,
            "base": {"sha": "base123"},
            "head": {"sha": "head456"},
        },
        "repository": {"full_name": "acme/shop"},
    }


def test_valid_signature_accepted():
    body = b'{"hello": "world"}'
    assert verify_signature(SECRET, body, sign(body))


def test_bad_signature_rejected():
    body = b'{"hello": "world"}'
    assert not verify_signature(SECRET, body, sign(body, "wrong-secret"))
    assert not verify_signature(SECRET, b"tampered body", sign(body))


def test_missing_signature_or_secret_rejected():
    body = b"{}"
    assert not verify_signature(SECRET, body, None)
    assert not verify_signature(SECRET, body, "")
    assert not verify_signature("", body, sign(body, ""))


def test_parse_relevant_actions():
    for action in ("opened", "reopened", "synchronize"):
        event = parse_pr_event("pull_request", "d-1", pr_payload(action))
        assert event is not None
        assert event.repository == "acme/shop"
        assert event.pr_number == 42
        assert event.head_sha == "head456"
        assert event.action == action


def test_irrelevant_actions_and_events_ignored():
    assert parse_pr_event("pull_request", "d", pr_payload("closed")) is None
    assert parse_pr_event("pull_request", "d", pr_payload("labeled")) is None
    assert parse_pr_event("push", "d", pr_payload()) is None
    assert parse_pr_event("issues", "d", {"action": "opened"}) is None


def test_malformed_payload_ignored():
    assert parse_pr_event("pull_request", "d", {"action": "opened"}) is None
    assert parse_pr_event("pull_request", "d", {"action": "opened", "pull_request": {"number": "x"}, "repository": {}}) is None
