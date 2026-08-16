"""Mine merged PRs into CANDIDATE benchmark records.

Ground-truth stance: the *low-risk suggestion* comes only from historical
survival — the PR merged at least ``min_age_days`` ago into an active repo
and was never the subject of an advisory we can see. It is deliberately NOT
based on Guardian's own risk score: selecting benchmark negatives with the
tool under evaluation would make the false-positive rate circular.

Path classifiers are reused for the *category* suggestion only (which kind
of change this is), never for the risky/not-risky label. Every mined record
is a CANDIDATE until a human promotes it with ``guardian-bench confirm``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

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
from guardian.models.pr import PRContext
from guardian.services.feature_extractor import extract_features

logger = logging.getLogger(__name__)

MAX_DIFF_LINES = 1_000


def record_id_for(repository: str, pr_number: int) -> str:
    return f"mined-{repository.replace('/', '-').lower()}-pr{pr_number}"


def suggest_category(diff_text: str) -> BenchmarkCategory:
    """Suggest the change *kind* from file paths (not a risk judgment)."""
    pr = PRContext(files=parse_diff(diff_text))
    features = extract_features(pr)
    if features.auth_files:
        return BenchmarkCategory.AUTH_CHANGE
    if features.database_files:
        return BenchmarkCategory.DATABASE_CHANGE
    if features.api_files:
        return BenchmarkCategory.API_CHANGE
    if features.source_files and not features.test_files:
        return BenchmarkCategory.TESTING_DEFICIENCY
    return BenchmarkCategory.NORMAL


def build_mined_record(
    repository: str,
    pr_meta: dict,
    diff_text: str,
    license_spdx: str = "",
    min_age_days: int = 180,
    max_diff_lines: int = MAX_DIFF_LINES,
    today: date | None = None,
) -> tuple[BenchmarkRecord, str]:
    """Turn one merged PR into a CANDIDATE record, or raise ``ValueError``."""
    pr_number = int(pr_meta["number"])
    merged_at_raw = pr_meta.get("merged_at")
    if not merged_at_raw:
        raise ValueError(f"PR #{pr_number} was not merged")

    merged_at = datetime.fromisoformat(str(merged_at_raw).replace("Z", "+00:00"))
    today = today or datetime.now(timezone.utc).date()
    age_days = (today - merged_at.date()).days
    if age_days < min_age_days:
        raise ValueError(f"PR #{pr_number} merged only {age_days} days ago (< {min_age_days})")

    if not diff_text.strip():
        raise ValueError(f"PR #{pr_number} has an empty diff")
    if len(diff_text.splitlines()) > max_diff_lines:
        raise ValueError(f"PR #{pr_number} diff too large to review")
    files = parse_diff(diff_text)
    if not files:
        raise ValueError(f"PR #{pr_number} diff has no parseable changes")

    record = BenchmarkRecord(
        id=record_id_for(repository, pr_number),
        category=suggest_category(diff_text),
        is_risky=False,  # suggestion from survival; a human confirms or overrides
        source=SourceKind.MINED,
        direction=DiffDirection.AS_MERGED,
        label_status=LabelStatus.CANDIDATE,
        provenance=Provenance(
            repository=repository,
            pr_number=pr_number,
            commit_sha=str(pr_meta.get("merge_commit_sha") or ""),
            license_spdx=license_spdx,
            retrieved_at=today.isoformat(),
            url=str(pr_meta.get("html_url") or f"https://github.com/{repository}/pull/{pr_number}"),
        ),
        notes=(
            f"Mined merged PR (merged {merged_at.date().isoformat()}, {age_days} days ago). "
            "Low-risk suggestion is based on survival age only, not on Guardian's score. "
            "CANDIDATE until human review via guardian-bench confirm."
        ),
    )
    return record, diff_text


def collect_mined_records(
    github: GitHubClient,
    repository: str,
    limit: int = 20,
    skip_ids: set[str] | None = None,
    min_age_days: int = 180,
    max_pages: int = 3,
) -> list[tuple[BenchmarkRecord, str]]:
    """Oldest-first sweep of closed PRs — old survivors are the point."""
    skip_ids = skip_ids or set()
    license_spdx = github.get_repo_license(repository)
    collected: list[tuple[BenchmarkRecord, str]] = []

    for page in range(1, max_pages + 1):
        if len(collected) >= limit:
            break
        pulls = github.list_pulls(repository, page=page)
        if not pulls:
            break
        for pr_meta in pulls:
            if len(collected) >= limit:
                break
            pr_number = int(pr_meta.get("number", 0))
            if record_id_for(repository, pr_number) in skip_ids:
                continue
            if not pr_meta.get("merged_at"):
                continue
            try:
                diff_text = github.get_pr_diff(repository, pr_number)
                record, diff = build_mined_record(
                    repository, pr_meta, diff_text, license_spdx, min_age_days=min_age_days
                )
            except ValueError as exc:
                logger.info("skipping: %s", exc)
                continue
            except Exception as exc:  # noqa: BLE001 — one bad PR must not stop the sweep
                logger.warning("fetch failed for %s#%d: %s", repository, pr_number, exc)
                continue
            collected.append((record, diff))
            logger.info("collected %s (%s)", record.id, record.category.value)
    return collected
