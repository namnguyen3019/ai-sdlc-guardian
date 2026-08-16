import csv
import json

import pytest

from guardian.benchmark.dataset import save_record
from guardian.benchmark.runner import Arm, arm_config, evaluate, save_results
from guardian.benchmark.schema import (
    BenchmarkCategory,
    BenchmarkRecord,
    LabelStatus,
    Provenance,
    SourceKind,
)
from guardian.bedrock.provider import StubProvider

# Multi-signal risky change: payment module (critical path) + SQL string
# interpolation + hardcoded secret + disabled TLS. A single lone finding
# deliberately does NOT cross the MEDIUM threshold under dimension weighting.
RISKY_DIFF = (
    "diff --git a/src/payment/db_service.py b/src/payment/db_service.py\n"
    "--- a/src/payment/db_service.py\n"
    "+++ b/src/payment/db_service.py\n"
    "@@ -10,3 +10,4 @@\n"
    "-    cur.execute(query, params)\n"
    '+    cur.execute(f"SELECT * FROM payments WHERE user_id = {uid}")\n'
    '+    api_key = "sk_live_secretsecret123"\n'
    "+    requests.post(url, verify=False)\n"
)
SAFE_DIFF = (
    "diff --git a/README.md b/README.md\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -1,1 +1,2 @@\n"
    " # App\n"
    "+Better docs.\n"
)


def record(record_id, risky, status=LabelStatus.CONFIRMED):
    return BenchmarkRecord(
        id=record_id,
        category=BenchmarkCategory.SECURITY if risky else BenchmarkCategory.NORMAL,
        is_risky=risky,
        source=SourceKind.CURATED_OSV if risky else SourceKind.MINED,
        label_status=status,
        provenance=Provenance(repository="acme/app", commit_sha="abc", advisory_id="GHSA-x"),
    )


@pytest.fixture
def dataset(tmp_path):
    save_record(tmp_path, record("osv-risky-1", True), RISKY_DIFF)
    save_record(tmp_path, record("mined-safe-1", False), SAFE_DIFF)
    save_record(tmp_path, record("mined-candidate", False, LabelStatus.CANDIDATE), SAFE_DIFF)
    return tmp_path


def test_arm_configs():
    assert arm_config(Arm.DETERMINISTIC).ai_enabled is False
    llm_only = arm_config(Arm.LLM_ONLY)
    assert llm_only.weights.ai_risk == 1.0 and llm_only.weights.security == 0.0
    assert arm_config(Arm.GATED_HYBRID).ai_escalation_gate is True
    assert arm_config(Arm.HYBRID).ai_escalation_gate is False


def test_arm_a_deterministic(dataset):
    results = evaluate(dataset, Arm.DETERMINISTIC)
    # Candidates are excluded: 2 confirmed records evaluated, not 3.
    assert results["metrics"]["records"] == 2
    by_id = {o["record_id"]: o for o in results["outcomes"]}
    assert by_id["osv-risky-1"]["predicted_risky"] is True  # SQL injection caught
    assert by_id["mined-safe-1"]["predicted_risky"] is False
    assert results["metrics"]["confusion"] == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert results["experiment"]["model_id"] is None


def test_arm_b_requires_provider(dataset):
    with pytest.raises(ValueError, match="requires an LLM provider"):
        evaluate(dataset, Arm.LLM_ONLY)


def ai_flagging_response():
    return json.dumps(
        {
            "findings": [
                {
                    "category": "security",
                    "severity": "CRITICAL",
                    "confidence": 0.9,
                    "file": "src/payment/db_service.py",
                    "title": "Injection",
                    "explanation": "Interpolated SQL.",
                    "recommendation": "Parameterize.",
                    "evidence": 'cur.execute(f"SELECT * FROM payments WHERE user_id = {uid}")',
                }
            ]
        }
    )


def test_arm_b_llm_only_scores_from_ai_alone(dataset):
    # Records evaluate in sorted-id order: mined-safe-1 first, osv-risky-1 second.
    provider = StubProvider(['{"findings": []}', ai_flagging_response()])
    results = evaluate(dataset, Arm.LLM_ONLY, provider=provider)
    by_id = {o["record_id"]: o for o in results["outcomes"]}
    assert by_id["osv-risky-1"]["predicted_risky"] is True
    assert by_id["osv-risky-1"]["ai_ran"] is True
    assert by_id["mined-safe-1"]["predicted_risky"] is False
    # Deterministic analyzers were off: the risky record's findings are AI-only.
    assert by_id["osv-risky-1"]["findings_total"] == 1


def test_arm_d_gate_skips_safe_records(dataset):
    provider = StubProvider([ai_flagging_response()])
    results = evaluate(dataset, Arm.GATED_HYBRID, provider=provider)
    by_id = {o["record_id"]: o for o in results["outcomes"]}
    # Risky record escalates to the model; the docs-only record is gated.
    assert by_id["osv-risky-1"]["ai_ran"] is True
    assert by_id["mined-safe-1"]["ai_skipped_by_gate"] is True
    assert results["metrics"]["ai"] == {"ran": 1, "skipped_by_gate": 1}


def test_invalid_dataset_refused(dataset):
    (dataset / "diffs" / "osv-risky-1.diff").unlink()
    with pytest.raises(ValueError, match="dataset invalid"):
        evaluate(dataset, Arm.DETERMINISTIC)


def test_save_results_exports(dataset, tmp_path):
    results = evaluate(dataset, Arm.DETERMINISTIC)
    out = tmp_path / "results" / "armA"
    save_results(results, out)

    assert json.loads((out / "metrics.json").read_text())["records"] == 2
    experiment = json.loads((out / "experiment.json").read_text())
    assert experiment["arm"] == "A"
    assert experiment["engine_version"]
    with (out / "outcomes.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["record_id"] for row in rows} == {"osv-risky-1", "mined-safe-1"}
