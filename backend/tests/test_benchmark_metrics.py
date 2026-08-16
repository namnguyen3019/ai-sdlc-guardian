import pytest

from guardian.benchmark.metrics import RecordOutcome, compute_metrics, wilson_interval


def outcome(record_id, truth, predicted, **overrides):
    fields = dict(
        record_id=record_id,
        category="security",
        split="calibration",
        ground_truth_risky=truth,
        predicted_risky=predicted,
        overall_risk=None if predicted is None else (70 if predicted else 5),
        duration_ms=10,
    )
    fields.update(overrides)
    return RecordOutcome(**fields)


def test_wilson_interval_basics():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(8, 10)
    assert low < 0.8 < high
    assert 0.0 <= low and high <= 1.0
    # Small n → wide interval; that's the point.
    low_small, high_small = wilson_interval(4, 5)
    assert (high_small - low_small) > (high - low)


def test_perfect_classifier():
    outcomes = [outcome("r1", True, True), outcome("n1", False, False)]
    metrics = compute_metrics(outcomes)
    assert metrics["confusion"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["accuracy"] == 1.0


def test_mixed_classifier():
    outcomes = [
        outcome("tp1", True, True),
        outcome("tp2", True, True),
        outcome("fn1", True, False),
        outcome("fp1", False, True),
        outcome("tn1", False, False),
    ]
    metrics = compute_metrics(outcomes)
    assert metrics["precision"] == pytest.approx(2 / 3, abs=1e-3)
    assert metrics["recall"] == pytest.approx(2 / 3, abs=1e-3)
    assert metrics["f1"] == pytest.approx(2 / 3, abs=1e-3)
    assert metrics["false_negative_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert metrics["precision_ci95"] is not None


def test_undefined_metrics_are_none_not_zero():
    # All-risky dataset: no negatives → FPR undefined, precision defined.
    metrics = compute_metrics([outcome("r1", True, True), outcome("r2", True, False)])
    assert metrics["false_positive_rate"] is None
    assert metrics["false_positive_rate_ci95"] is None
    assert metrics["recall"] == 0.5
    # No predictions at all → everything undefined.
    empty = compute_metrics([outcome("e1", True, None, error="boom")])
    assert empty["scored"] == 0 and empty["errored"] == 1
    assert empty["precision"] is None and empty["accuracy"] is None


def test_cost_latency_and_ai_accounting():
    outcomes = [
        outcome("a", True, True, duration_ms=100, estimated_cost_usd=0.01,
                input_tokens=1000, output_tokens=100, ai_ran=True),
        outcome("b", True, True, duration_ms=300, ai_skipped_by_gate=True),
    ]
    metrics = compute_metrics(outcomes)
    assert metrics["latency_ms"]["mean"] == 200.0
    assert metrics["cost_usd"]["total"] == 0.01
    assert metrics["tokens"] == {"input": 1000, "output": 100}
    assert metrics["ai"] == {"ran": 1, "skipped_by_gate": 1}
