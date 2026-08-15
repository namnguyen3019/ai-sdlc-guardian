import json

import pytest

from guardian.github.client import GitHubClient, GitHubError, HTTPCall


class FakeTransport:
    """Records calls; replies from a {(method, path): (status, body)} table."""

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[HTTPCall] = []

    def __call__(self, call: HTTPCall):
        self.calls.append(call)
        path = call.url.replace("https://api.github.com", "")
        status, body = self.routes[(call.method, path)]
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        return status, payload


def test_get_pr_sends_auth_and_parses():
    transport = FakeTransport({("GET", "/repos/acme/shop/pulls/42"): (200, {"number": 42, "title": "t"})})
    pr = GitHubClient("tok", transport=transport).get_pr("acme/shop", 42)
    assert pr["number"] == 42
    call = transport.calls[0]
    assert call.headers["Authorization"] == "Bearer tok"
    assert "github" in call.headers["Accept"]


def test_get_pr_diff_uses_diff_accept_header():
    transport = FakeTransport({("GET", "/repos/acme/shop/pulls/42"): (200, b"diff --git a/x b/x\n")})
    diff = GitHubClient("tok", transport=transport).get_pr_diff("acme/shop", 42)
    assert diff.startswith("diff --git")
    assert transport.calls[0].headers["Accept"] == "application/vnd.github.v3.diff"


def test_error_status_raises():
    transport = FakeTransport({("GET", "/repos/acme/shop/pulls/42"): (404, {"message": "Not Found"})})
    with pytest.raises(GitHubError) as excinfo:
        GitHubClient("tok", transport=transport).get_pr("acme/shop", 42)
    assert excinfo.value.status == 404


def test_upsert_creates_when_no_marker_found():
    transport = FakeTransport(
        {
            ("GET", "/repos/acme/shop/issues/42/comments?per_page=100"): (200, [{"id": 1, "body": "unrelated"}]),
            ("POST", "/repos/acme/shop/issues/42/comments"): (201, {"id": 99}),
        }
    )
    comment_id, action = GitHubClient("tok", transport=transport).upsert_marked_comment(
        "acme/shop", 42, "new body", "<!-- marker -->"
    )
    assert (comment_id, action) == (99, "created")
    post = transport.calls[-1]
    assert json.loads(post.body.decode()) == {"body": "new body"}


def test_upsert_updates_existing_marked_comment():
    transport = FakeTransport(
        {
            ("GET", "/repos/acme/shop/issues/42/comments?per_page=100"): (
                200,
                [{"id": 7, "body": "<!-- marker -->\nold report"}],
            ),
            ("PATCH", "/repos/acme/shop/issues/comments/7"): (200, {"id": 7}),
        }
    )
    comment_id, action = GitHubClient("tok", transport=transport).upsert_marked_comment(
        "acme/shop", 42, "fresh body", "<!-- marker -->"
    )
    assert (comment_id, action) == (7, "updated")
    assert transport.calls[-1].method == "PATCH"
