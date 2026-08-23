#!/usr/bin/env python3
"""Generate frontend/public/data.json from real Guardian analyses.

Runs the deterministic engine over the benchmark dataset's diffs (no AWS, no
model calls) and summarizes the results into the dashboard payload. Every
number shown in the sample dashboard is genuine Guardian output.

For a live dashboard, replace this with a DynamoDB scan piped through
guardian.dashboard.from_dynamodb_items.

    python frontend/scripts/generate-sample-data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from guardian.benchmark.dataset import load_diff, load_records  # noqa: E402
from guardian.dashboard import from_reports  # noqa: E402
from guardian.github.diff_parser import parse_diff  # noqa: E402
from guardian.models.pr import PRContext  # noqa: E402
from guardian.services.analysis_service import AnalysisService  # noqa: E402

DATASET = ROOT / "benchmark" / "datasets" / "main"
OUTPUT = ROOT / "frontend" / "public" / "data.json"


def main() -> int:
    service = AnalysisService()
    reports = []
    for record in load_records(DATASET):
        try:
            diff_text = load_diff(DATASET, record)
        except FileNotFoundError:
            continue
        pr = PRContext(
            repository=record.provenance.repository or "benchmark/unknown",
            pr_number=record.provenance.pr_number or 0,
            files=parse_diff(diff_text),
        )
        reports.append(service.analyze(pr))

    data = from_reports(reports)
    data["note"] = (
        "Sample data: real deterministic Guardian output over the benchmark "
        "diffs (no AI arm). Replace with a DynamoDB scan for a live dashboard."
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} from {len(reports)} analyses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
