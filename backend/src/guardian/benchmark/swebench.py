"""Bug records from SWE-bench (princeton-nlp/SWE-bench).

Each SWE-bench instance is a real GitHub issue paired with the merged fix
patch, validated by tests — ground truth strong enough to confirm without
human review. As with OSV, the *reverse* of the fix is a change that
introduces the bug, giving category=bug positives.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
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
from guardian.github.diff_parser import parse_diff

logger = logging.getLogger(__name__)

ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "princeton-nlp/SWE-bench"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET}"
MAX_DIFF_LINES = 2_000
_PAGE = 100

FetchJson = Callable[[str], dict]


def _default_fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "ai-sdlc-guardian-benchmark"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def rows_url(offset: int, length: int = _PAGE, split: str = "test") -> str:
    query = urllib.parse.urlencode(
        {"dataset": DATASET, "config": "default", "split": split, "offset": offset, "length": length}
    )
    return f"{ROWS_API}?{query}"


def build_bug_record(row: dict, license_spdx: str = "") -> tuple[BenchmarkRecord, str]:
    """Reverse one SWE-bench fix patch into a CONFIRMED bug record."""
    instance_id = str(row.get("instance_id", "")).strip()
    repository = str(row.get("repo", "")).strip()
    patch = str(row.get("patch", ""))
    if not instance_id or not repository:
        raise ValueError("row lacks instance_id or repo")
    if not patch.strip():
        raise ValueError(f"{instance_id}: empty patch")
    if len(patch.splitlines()) > MAX_DIFF_LINES:
        raise ValueError(f"{instance_id}: patch too large to review")

    reversed_text = reverse_diff(patch)
    files = parse_diff(reversed_text)
    if not files or all(f.additions == 0 and f.deletions == 0 for f in files):
        raise ValueError(f"{instance_id}: reversed patch has no analyzable changes")

    record = BenchmarkRecord(
        id=f"swebench-{instance_id.lower()}",
        category=BenchmarkCategory.BUG,
        is_risky=True,
        source=SourceKind.CURATED_DATASET,
        direction=DiffDirection.REVERSED_FIX,
        label_status=LabelStatus.CONFIRMED,
        provenance=Provenance(
            repository=repository,
            commit_sha=str(row.get("base_commit", "")),
            license_spdx=license_spdx,
            retrieved_at=date.today().isoformat(),
            url=DATASET_URL,
        ),
        notes=(
            f"SWE-bench instance {instance_id}: reverse of the merged, test-validated "
            "fix patch — this change introduces the bug the issue describes."
        ),
    )
    return record, reversed_text


def collect_bug_records(
    fetch_json: FetchJson | None = None,
    limit: int = 40,
    skip_ids: set[str] | None = None,
    offset: int = 0,
    license_lookup: Callable[[str], str] | None = None,
    max_pages: int = 10,
) -> list[tuple[BenchmarkRecord, str]]:
    fetch_json = fetch_json or _default_fetch_json
    skip_ids = skip_ids or set()
    license_cache: dict[str, str] = {}
    collected: list[tuple[BenchmarkRecord, str]] = []

    for page in range(max_pages):
        if len(collected) >= limit:
            break
        try:
            payload = fetch_json(rows_url(offset + page * _PAGE))
        except Exception as exc:  # noqa: BLE001
            logger.warning("SWE-bench rows fetch failed at offset %d: %s", offset + page * _PAGE, exc)
            break
        rows = [item.get("row", {}) for item in payload.get("rows", [])]
        if not rows:
            break

        for row in rows:
            if len(collected) >= limit:
                break
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id or f"swebench-{instance_id.lower()}" in skip_ids:
                continue
            repository = str(row.get("repo", ""))
            if license_lookup is not None and repository not in license_cache:
                try:
                    license_cache[repository] = license_lookup(repository)
                except Exception:  # noqa: BLE001 — license metadata is best-effort
                    license_cache[repository] = ""
            try:
                record, diff_text = build_bug_record(row, license_cache.get(repository, ""))
            except (ReverseDiffError, ValueError) as exc:
                logger.info("skipping: %s", exc)
                continue
            collected.append((record, diff_text))
            logger.info("collected %s from %s", record.id, repository)
    return collected
