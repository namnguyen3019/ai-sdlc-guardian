"""Build advisory-backed security records from OSV.

Flow: GitHub's global advisory list → the matching OSV record (which carries
structured ``FIX`` references) → the fix commit's diff → reversed, so the
record *introduces* the vulnerability the advisory describes. Ground truth is
the advisory itself, so these records are born CONFIRMED.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Callable

from guardian.benchmark.reverse_diff import ReverseDiffError, reverse_diff
from guardian.benchmark.schema import (
    BenchmarkCategory,
    BenchmarkRecord,
    DiffDirection,
    LabelStatus,
    Provenance,
    SourceKind,
)
from guardian.github.client import GitHubClient
from guardian.github.diff_parser import parse_diff

logger = logging.getLogger(__name__)

OSV_API = "https://api.osv.dev/v1/vulns/"
_COMMIT_URL = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/commit/([0-9a-f]{7,40})")

# Keep records reviewable: a fix touching thousands of lines is not a useful
# benchmark item.
MAX_DIFF_LINES = 2_000

FetchJson = Callable[[str], dict]


def _default_fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "ai-sdlc-guardian-benchmark"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class FixCommit:
    advisory_id: str
    repository: str
    commit_sha: str
    cwe_ids: tuple[str, ...]
    url: str


def find_fix_commit(osv_record: dict) -> FixCommit | None:
    """Extract the GitHub fix commit from an OSV record, if any.

    GHSA-sourced records usually link the fix commit as a plain ``WEB``
    reference rather than ``FIX``, so both are accepted; ``FIX`` wins when
    present. The commit is named by the advisory itself either way, which is
    what makes the label CONFIRMED.
    """
    advisory_id = str(osv_record.get("id", ""))
    candidates: list[tuple[str, str, str]] = []  # (ref_type, repository, sha, url)
    for reference in osv_record.get("references", []) or []:
        ref_type = str(reference.get("type", ""))
        if ref_type not in ("FIX", "WEB"):
            continue
        match = _COMMIT_URL.match(str(reference.get("url", "")))
        if match:
            candidates.append((ref_type, match.group(1), match.group(2)))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0] != "FIX")  # FIX first
    ref_type, repository, sha = candidates[0]
    cwes = tuple(
        str(c) for c in (osv_record.get("database_specific", {}) or {}).get("cwe_ids", []) or []
    )
    return FixCommit(
        advisory_id=advisory_id,
        repository=repository,
        commit_sha=sha,
        cwe_ids=cwes,
        url=f"https://github.com/{repository}/commit/{sha}",
    )


def build_security_record(
    fix: FixCommit,
    diff_text: str,
    license_spdx: str = "",
) -> tuple[BenchmarkRecord, str]:
    """Reverse the fix diff and wrap it in a CONFIRMED security record.

    Raises ``ReverseDiffError``/``ValueError`` for unusable diffs (binary,
    empty, oversized) — callers skip those advisories.
    """
    if not diff_text.strip():
        raise ValueError(f"{fix.advisory_id}: empty diff")
    if len(diff_text.splitlines()) > MAX_DIFF_LINES:
        raise ValueError(f"{fix.advisory_id}: diff too large to review")

    reversed_text = reverse_diff(diff_text)
    files = parse_diff(reversed_text)
    if not files or all(f.additions == 0 and f.deletions == 0 for f in files):
        raise ValueError(f"{fix.advisory_id}: reversed diff has no analyzable changes")

    record = BenchmarkRecord(
        id=f"osv-{fix.advisory_id.lower()}",
        category=BenchmarkCategory.SECURITY,
        is_risky=True,
        source=SourceKind.CURATED_OSV,
        direction=DiffDirection.REVERSED_FIX,
        label_status=LabelStatus.CONFIRMED,
        provenance=Provenance(
            repository=fix.repository,
            commit_sha=fix.commit_sha,
            advisory_id=fix.advisory_id,
            cwe_ids=list(fix.cwe_ids),
            license_spdx=license_spdx,
            retrieved_at=date.today().isoformat(),
            url=fix.url,
        ),
        notes="Reverse of the advisory's fix commit: this change introduces the vulnerability.",
    )
    return record, reversed_text


def collect_security_records(
    advisory_ids: list[str],
    github: GitHubClient,
    fetch_json: FetchJson | None = None,
    limit: int = 20,
    skip_ids: set[str] | None = None,
) -> list[tuple[BenchmarkRecord, str]]:
    """Resolve advisories → OSV records → reversed fix diffs.

    Best-effort: advisories without a usable GitHub fix commit are skipped
    with a log line, never fabricated.
    """
    fetch_json = fetch_json or _default_fetch_json
    skip_ids = skip_ids or set()
    collected: list[tuple[BenchmarkRecord, str]] = []

    for advisory_id in advisory_ids:
        if len(collected) >= limit:
            break
        record_id = f"osv-{advisory_id.lower()}"
        if record_id in skip_ids:
            continue
        try:
            osv_record = fetch_json(f"{OSV_API}{advisory_id}")
        except Exception as exc:  # noqa: BLE001 — one bad advisory must not stop the batch
            logger.warning("OSV lookup failed for %s: %s", advisory_id, exc)
            continue

        fix = find_fix_commit(osv_record)
        if fix is None:
            logger.info("skipping %s: no GitHub fix commit reference", advisory_id)
            continue

        try:
            diff_text = github.get_commit_diff(fix.repository, fix.commit_sha)
            license_spdx = github.get_repo_license(fix.repository)
            record, reversed_text = build_security_record(fix, diff_text, license_spdx)
        except (ReverseDiffError, ValueError) as exc:
            logger.info("skipping %s: %s", advisory_id, exc)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch failed for %s (%s@%s): %s", advisory_id, fix.repository, fix.commit_sha, exc)
            continue

        collected.append((record, reversed_text))
        logger.info("collected %s from %s@%s", record.id, fix.repository, fix.commit_sha[:12])
    return collected
