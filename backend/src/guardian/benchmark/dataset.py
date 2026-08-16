"""Dataset storage: one JSONL file of records + sidecar diff files."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from guardian.benchmark.schema import BenchmarkRecord

RECORDS_FILENAME = "records.jsonl"
DIFFS_DIRNAME = "diffs"


def dataset_paths(dataset_dir: str | Path) -> tuple[Path, Path]:
    root = Path(dataset_dir)
    return root / RECORDS_FILENAME, root / DIFFS_DIRNAME


def save_record(dataset_dir: str | Path, record: BenchmarkRecord, diff_text: str) -> None:
    records_path, diffs_dir = dataset_paths(dataset_dir)
    diffs_dir.mkdir(parents=True, exist_ok=True)
    (diffs_dir / record.diff_filename).write_text(diff_text, encoding="utf-8")
    with records_path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def load_records(dataset_dir: str | Path) -> list[BenchmarkRecord]:
    records_path, _ = dataset_paths(dataset_dir)
    if not records_path.exists():
        return []
    records: list[BenchmarkRecord] = []
    for line in records_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(BenchmarkRecord.model_validate_json(line))
    return records


def load_diff(dataset_dir: str | Path, record: BenchmarkRecord) -> str:
    _, diffs_dir = dataset_paths(dataset_dir)
    return (diffs_dir / record.diff_filename).read_text(encoding="utf-8")


def existing_ids(dataset_dir: str | Path) -> set[str]:
    return {record.id for record in load_records(dataset_dir)}


def update_record(dataset_dir: str | Path, updated: BenchmarkRecord) -> None:
    """Replace one record in the JSONL file (used by label confirmation)."""
    records_path, _ = dataset_paths(dataset_dir)
    records = load_records(dataset_dir)
    if updated.id not in {r.id for r in records}:
        raise KeyError(f"record {updated.id} not found in {dataset_dir}")
    with records_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write((updated if record.id == updated.id else record).model_dump_json() + "\n")


def composition(records: list[BenchmarkRecord]) -> dict:
    """Counts used by ``guardian-bench stats`` and the dataset README."""
    return {
        "total": len(records),
        "by_category": dict(Counter(r.category.value for r in records)),
        "by_source": dict(Counter(r.source.value for r in records)),
        "by_label_status": dict(Counter(r.label_status.value for r in records)),
        "by_split": dict(Counter(r.split.value for r in records)),
        "risky": sum(1 for r in records if r.is_risky),
        "not_risky": sum(1 for r in records if not r.is_risky),
    }
