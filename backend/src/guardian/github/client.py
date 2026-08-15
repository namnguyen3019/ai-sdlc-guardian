"""Minimal GitHub REST client (stdlib urllib, no extra dependencies).

The HTTP transport is injectable so every test runs offline. Only the
endpoints Guardian needs: PR metadata, PR diff, and issue comments.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

Transport = Callable[["HTTPCall"], tuple[int, bytes]]

_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # a 10 MB diff is already far past analyzable


class HTTPCall:
    def __init__(self, method: str, url: str, headers: dict[str, str], body: bytes | None) -> None:
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body


class GitHubError(RuntimeError):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def _urllib_transport(call: HTTPCall) -> tuple[int, bytes]:
    request = urllib.request.Request(call.url, data=call.body, headers=call.headers, method=call.method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read(_MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class GitHubClient:
    def __init__(self, token: str, api_url: str = "https://api.github.com", transport: Transport | None = None) -> None:
        self.token = token
        self.api_url = api_url.rstrip("/")
        self._transport = transport or _urllib_transport

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        accept: str = "application/vnd.github+json",
    ) -> tuple[int, bytes]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "User-Agent": "ai-sdlc-guardian",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        if payload is not None:
            headers["Content-Type"] = "application/json"
        return self._transport(HTTPCall(method, f"{self.api_url}{path}", headers, payload))

    def _json(self, method: str, path: str, body: dict | None = None) -> dict | list:
        status, raw = self._request(method, path, body)
        if status >= 400:
            raise GitHubError(f"GitHub API {method} {path} failed with {status}", status)
        return json.loads(raw.decode("utf-8")) if raw else {}

    # ------------------------------------------------------------- pull requests
    def get_pr(self, repository: str, pr_number: int) -> dict:
        data = self._json("GET", f"/repos/{repository}/pulls/{pr_number}")
        assert isinstance(data, dict)
        return data

    def get_pr_diff(self, repository: str, pr_number: int) -> str:
        status, raw = self._request(
            "GET", f"/repos/{repository}/pulls/{pr_number}", accept="application/vnd.github.v3.diff"
        )
        if status >= 400:
            raise GitHubError(f"fetching diff for {repository}#{pr_number} failed with {status}", status)
        return raw.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------ comments
    def list_issue_comments(self, repository: str, pr_number: int) -> list[dict]:
        # First page of 100 is ample: the Guardian comment is posted early in a
        # PR's life and edited in place afterwards.
        data = self._json("GET", f"/repos/{repository}/issues/{pr_number}/comments?per_page=100")
        assert isinstance(data, list)
        return data

    def create_comment(self, repository: str, pr_number: int, body: str) -> dict:
        data = self._json("POST", f"/repos/{repository}/issues/{pr_number}/comments", {"body": body})
        assert isinstance(data, dict)
        return data

    def update_comment(self, repository: str, comment_id: int, body: str) -> dict:
        data = self._json("PATCH", f"/repos/{repository}/issues/comments/{comment_id}", {"body": body})
        assert isinstance(data, dict)
        return data

    def upsert_marked_comment(self, repository: str, pr_number: int, body: str, marker: str) -> tuple[int, str]:
        """Create the marked comment or update it in place.

        Returns (comment_id, "created" | "updated"). This is what prevents
        duplicate Guardian comments on every push.
        """
        for comment in self.list_issue_comments(repository, pr_number):
            if marker in str(comment.get("body", "")):
                updated = self.update_comment(repository, int(comment["id"]), body)
                return int(updated.get("id", comment["id"])), "updated"
        created = self.create_comment(repository, pr_number, body)
        return int(created["id"]), "created"
