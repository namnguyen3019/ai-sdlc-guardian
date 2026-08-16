"""Dataset validation — run before any evaluation and in CI.

A dataset that fails validation must not produce published numbers.
"""

from __future__ import annotations

from pathlib import Path

from guardian.benchmark.dataset import dataset_paths, load_records
from guardian.benchmark.schema import BenchmarkRecord, LabelStatus, SourceKind
from guardian.github.diff_parser import parse_diff


def validate_dataset(dataset_dir: str | Path) -> list[str]:
    """Return a list of problems; empty means the dataset is sound."""
    problems: list[str] = []
    records_path, diffs_dir = dataset_paths(dataset_dir)
    if not records_path.exists():
        return [f"missing {records_path}"]

    try:
        records = load_records(dataset_dir)
    except Exception as exc:  # noqa: BLE001 — surfaced as a validation problem
        return [f"records file unreadable: {exc}"]

    seen_ids: set[str] = set()
    for record in records:
        prefix = f"record {record.id}"
        if record.id in seen_ids:
            problems.append(f"{prefix}: duplicate id")
            continue
        seen_ids.add(record.id)

        diff_path = diffs_dir / record.diff_filename
        if not diff_path.exists():
            problems.append(f"{prefix}: missing diff file {diff_path.name}")
            continue

        try:
            files = parse_diff(diff_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{prefix}: diff does not parse: {exc}")
            continue
        if not files:
            problems.append(f"{prefix}: diff parses to zero file changes")

        problems.extend(f"{prefix}: {issue}" for issue in _label_issues(record))

    known = {record.diff_filename for record in records}
    if diffs_dir.exists():
        for orphan in sorted(p.name for p in diffs_dir.glob("*.diff") if p.name not in known):
            problems.append(f"orphan diff file with no record: {orphan}")

    return problems


def _label_issues(record: BenchmarkRecord) -> list[str]:
    issues: list[str] = []
    if record.label_status == LabelStatus.CONFIRMED:
        if record.source in (SourceKind.CURATED_OSV, SourceKind.CURATED_DATASET):
            if not record.provenance.advisory_id and not record.provenance.url:
                issues.append("confirmed curated record lacks advisory id or source url")
        if not record.provenance.repository:
            issues.append("confirmed record lacks source repository")
        if not record.provenance.commit_sha and record.provenance.pr_number is None:
            issues.append("confirmed record lacks commit sha or PR number")
    if record.source == SourceKind.SYNTHETIC and record.label_status != LabelStatus.CONFIRMED:
        issues.append("synthetic records have known ground truth; must be confirmed")
    return issues


def evaluation_ready(records: list[BenchmarkRecord]) -> list[BenchmarkRecord]:
    """The subset evaluation runs are allowed to use."""
    return [r for r in records if r.label_status == LabelStatus.CONFIRMED]
