"""GitHub webhook verification and event parsing.

Signature verification is the authentication for the webhook endpoint:
constant-time HMAC-SHA256 against the shared secret, checked before the
payload is parsed at all. Payload fields are attacker-influenced data and are
only ever treated as identifiers, never as instructions.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

# PR lifecycle actions that trigger an analysis.
ANALYZED_ACTIONS = frozenset({"opened", "reopened", "synchronize"})


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Validate ``X-Hub-Signature-256`` in constant time."""
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


@dataclass(frozen=True)
class PREvent:
    repository: str
    pr_number: int
    action: str
    base_sha: str
    head_sha: str
    delivery_id: str


def parse_pr_event(event_name: str, delivery_id: str, payload: dict) -> PREvent | None:
    """Extract the analysis trigger, or ``None`` for events Guardian ignores."""
    if event_name != "pull_request":
        return None
    action = str(payload.get("action", ""))
    if action not in ANALYZED_ACTIONS:
        return None

    pull_request = payload.get("pull_request") or {}
    repository = (payload.get("repository") or {}).get("full_name", "")
    pr_number = pull_request.get("number")
    if not repository or not isinstance(pr_number, int):
        return None

    return PREvent(
        repository=str(repository),
        pr_number=pr_number,
        action=action,
        base_sha=str((pull_request.get("base") or {}).get("sha", "")),
        head_sha=str((pull_request.get("head") or {}).get("sha", "")),
        delivery_id=delivery_id,
    )
