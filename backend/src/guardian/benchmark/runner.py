"""Evaluation runner — the four benchmark arms on identical inputs.

Arms:
    A  deterministic-only      (no model, free)
    B  LLM-only                (no deterministic analyzers; all weight on AI)
    C  hybrid                  (Guardian's default configuration)
    D  gated hybrid            (hybrid + deterministic escalation gate)

Discipline enforced here, not left to good intentions:

* Only CONFIRMED records are evaluated (`evaluation_ready`).
* The runner never mutates records or splits; the split is recomputed from
  each record id.
* Results are written with the full effective config, engine version, and
  dataset composition, so any number in a report can be regenerated.
"""

from __future__ import annotations

import csv
import json
import logging
from enum import Enum
from pathlib import Path

import guardian
from guardian.benchmark.dataset import composition, load_diff, load_records
from guardian.benchmark.metrics import RecordOutcome, compute_metrics
from guardian.benchmark.schema import BenchmarkRecord, Split
from guardian.benchmark.validate import evaluation_ready, validate_dataset
from guardian.bedrock.provider import LLMProvider
from guardian.github.diff_parser import parse_diff
from guardian.models.config import GuardianConfig, ScoringWeights
from guardian.models.pr import PRContext
from guardian.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)

# MEDIUM boundary: a PR scoring 31+ is "flagged risky" for classification.
DEFAULT_THRESHOLD = 31


class Arm(str, Enum):
    DETERMINISTIC = "A"
    LLM_ONLY = "B"
    HYBRID = "C"
    GATED_HYBRID = "D"

    @property
    def needs_provider(self) -> bool:
        return self is not Arm.DETERMINISTIC


def arm_config(arm: Arm, base: GuardianConfig | None = None) -> GuardianConfig:
    config = (base or GuardianConfig()).model_copy(deep=True)
    if arm is Arm.DETERMINISTIC:
        config.ai_enabled = False
    elif arm is Arm.LLM_ONLY:
        config.ai_enabled = True
        config.ai_escalation_gate = False
        config.weights = ScoringWeights(
            security=0.0, testing=0.0, change_impact=0.0, complexity=0.0, ai_risk=1.0
        )
    elif arm is Arm.HYBRID:
        config.ai_enabled = True
        config.ai_escalation_gate = False
    elif arm is Arm.GATED_HYBRID:
        config.ai_enabled = True
        config.ai_escalation_gate = True
    return config


def arm_service(arm: Arm, config: GuardianConfig, provider: LLMProvider | None) -> AnalysisService:
    if arm.needs_provider and provider is None:
        raise ValueError(f"arm {arm.value} requires an LLM provider")
    if arm is Arm.DETERMINISTIC:
        return AnalysisService(config)
    if arm is Arm.LLM_ONLY:
        return AnalysisService(config, analyzers=[], ai_provider=provider)
    return AnalysisService(config, ai_provider=provider)


def _select_records(
    dataset_dir: str | Path, split: Split | None, limit: int | None
) -> list[BenchmarkRecord]:
    records = evaluation_ready(load_records(dataset_dir))
    if split is not None:
        records = [r for r in records if r.split == split]
    records.sort(key=lambda r: r.id)  # deterministic order
    return records[:limit] if limit else records


def evaluate(
    dataset_dir: str | Path,
    arm: Arm,
    provider: LLMProvider | None = None,
    split: Split | None = None,
    threshold: int = DEFAULT_THRESHOLD,
    limit: int | None = None,
    base_config: GuardianConfig | None = None,
) -> dict:
    """Run one arm over the dataset; returns the full results document."""
    problems = validate_dataset(dataset_dir)
    if problems:
        raise ValueError(f"dataset invalid ({len(problems)} problems); run guardian-bench validate")

    config = arm_config(arm, base_config)
    service = arm_service(arm, config, provider)
    records = _select_records(dataset_dir, split, limit)
    if not records:
        raise ValueError("no confirmed records selected — nothing to evaluate")

    outcomes: list[RecordOutcome] = []
    for record in records:
        outcomes.append(_evaluate_record(service, dataset_dir, record, threshold))

    return {
        "experiment": {
            "arm": arm.value,
            "arm_name": arm.name.lower(),
            "engine_version": guardian.__version__,
            "threshold": threshold,
            "split": split.value if split else "all",
            "dataset_dir": str(dataset_dir),
            "dataset_composition": composition(records),
            "model_id": config.bedrock_model_id if arm.needs_provider else None,
            "config": config.model_dump(),
        },
        "metrics": compute_metrics(outcomes),
        "outcomes": [outcome.model_dump() for outcome in outcomes],
    }


def _evaluate_record(
    service: AnalysisService,
    dataset_dir: str | Path,
    record: BenchmarkRecord,
    threshold: int,
) -> RecordOutcome:
    base = RecordOutcome(
        record_id=record.id,
        category=record.category.value,
        split=record.split.value,
        ground_truth_risky=record.is_risky,
    )
    try:
        diff_text = load_diff(dataset_dir, record)
        pr = PRContext(repository=record.provenance.repository or "benchmark/unknown",
                      pr_number=record.provenance.pr_number or 0,
                      files=parse_diff(diff_text))
        report = service.analyze(pr)
    except Exception as exc:  # noqa: BLE001 — an errored record is data, not a crash
        logger.exception("evaluation failed for %s", record.id)
        base.error = f"{type(exc).__name__}: {exc}"
        return base

    base.predicted_risky = report.overall_risk >= threshold
    base.overall_risk = report.overall_risk
    base.risk_level = report.risk_level.value
    base.findings_total = len(report.findings)
    base.duration_ms = report.duration_ms
    if report.analyzer_failures:
        base.error = "; ".join(f"{f.analyzer}: {f.error}" for f in report.analyzer_failures)
    if report.ai is not None:
        base.ai_ran = report.ai.ran
        base.ai_skipped_by_gate = report.ai.skipped_by_gate
        base.input_tokens = report.ai.input_tokens
        base.output_tokens = report.ai.output_tokens
        base.estimated_cost_usd = report.ai.estimated_cost_usd
    return base


_CSV_FIELDS = list(RecordOutcome.model_fields)


def save_results(results: dict, output_dir: str | Path) -> None:
    """experiment.json + metrics.json + outcomes.jsonl + outcomes.csv."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "experiment.json").write_text(json.dumps(results["experiment"], indent=2) + "\n")
    (out / "metrics.json").write_text(json.dumps(results["metrics"], indent=2) + "\n")
    with (out / "outcomes.jsonl").open("w", encoding="utf-8") as handle:
        for outcome in results["outcomes"]:
            handle.write(json.dumps(outcome) + "\n")
    with (out / "outcomes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results["outcomes"])
