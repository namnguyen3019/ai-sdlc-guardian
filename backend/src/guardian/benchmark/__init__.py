"""Benchmark dataset tooling (Week 4).

The dataset is the ground truth for evaluating Guardian's three (plus gated)
analysis arms. Rules that keep it honest:

* Every record carries provenance (source repo, SHAs, advisory id, license).
* Labels are either CONFIRMED (backed by historical evidence: an advisory,
  a revert, a traced fix) or CANDIDATE (heuristic, awaiting human review) —
  evaluation runs refuse candidates.
* Calibration/holdout splits are deterministic functions of the record id,
  so they cannot be cherry-picked after looking at results.
* Synthetic records are marked as synthetic and reported separately.
"""

from guardian.benchmark.schema import (
    BenchmarkCategory,
    BenchmarkRecord,
    DiffDirection,
    LabelStatus,
    Provenance,
    SourceKind,
    Split,
)

__all__ = [
    "BenchmarkCategory",
    "BenchmarkRecord",
    "DiffDirection",
    "LabelStatus",
    "Provenance",
    "SourceKind",
    "Split",
]
