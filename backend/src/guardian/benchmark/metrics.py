"""Classification metrics for evaluation runs.

Small-n honesty: metrics whose denominator is empty are ``None`` (never 0 or
1 by convention), and every proportion carries a 95% Wilson interval so a
recall of 0.8 on five records reads as the weak evidence it is.
"""

from __future__ import annotations

import math
from statistics import mean, median

from pydantic import BaseModel

_Z = 1.959964  # 95%


class RecordOutcome(BaseModel):
    record_id: str
    category: str
    split: str
    ground_truth_risky: bool
    predicted_risky: bool | None = None  # None → analysis errored
    overall_risk: int | None = None
    risk_level: str = ""
    findings_total: int = 0
    duration_ms: int = 0
    ai_ran: bool = False
    ai_skipped_by_gate: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: str = ""


def wilson_interval(successes: int, trials: int) -> tuple[float, float] | None:
    if trials == 0:
        return None
    p = successes / trials
    z2n = _Z * _Z / trials
    center = (p + z2n / 2) / (1 + z2n)
    half = (_Z / (1 + z2n)) * math.sqrt(p * (1 - p) / trials + z2n / (4 * trials))
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def compute_metrics(outcomes: list[RecordOutcome]) -> dict:
    scored = [o for o in outcomes if o.predicted_risky is not None]
    errored = [o for o in outcomes if o.predicted_risky is None]

    tp = sum(1 for o in scored if o.ground_truth_risky and o.predicted_risky)
    fn = sum(1 for o in scored if o.ground_truth_risky and not o.predicted_risky)
    fp = sum(1 for o in scored if not o.ground_truth_risky and o.predicted_risky)
    tn = sum(1 for o in scored if not o.ground_truth_risky and not o.predicted_risky)

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = round(2 * precision * recall / (precision + recall), 4)

    latencies = [o.duration_ms for o in scored]
    costs = [o.estimated_cost_usd for o in scored]

    return {
        "records": len(outcomes),
        "scored": len(scored),
        "errored": len(errored),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": precision,
        "precision_ci95": wilson_interval(tp, tp + fp),
        "recall": recall,
        "recall_ci95": wilson_interval(tp, tp + fn),
        "f1": f1,
        "false_positive_rate": _ratio(fp, fp + tn),
        "false_positive_rate_ci95": wilson_interval(fp, fp + tn),
        "false_negative_rate": _ratio(fn, fn + tp),
        "false_negative_rate_ci95": wilson_interval(fn, fn + tp),
        "accuracy": _ratio(tp + tn, len(scored)),
        "latency_ms": {
            "mean": round(mean(latencies), 1) if latencies else None,
            "median": round(median(latencies), 1) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "cost_usd": {
            "total": round(sum(costs), 6),
            "mean": round(mean(costs), 6) if costs else None,
        },
        "tokens": {
            "input": sum(o.input_tokens for o in scored),
            "output": sum(o.output_tokens for o in scored),
        },
        "ai": {
            "ran": sum(1 for o in scored if o.ai_ran),
            "skipped_by_gate": sum(1 for o in scored if o.ai_skipped_by_gate),
        },
    }
