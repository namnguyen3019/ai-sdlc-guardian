# Benchmark framework

**Status: dataset collection in progress; first baseline measured.** The
pipeline (schema, fetcher, validator, splits, evaluation runner) is built and
tested; a 25-record confirmed seed batch is committed, and the free
deterministic arm has been run on its calibration split (results below).
**Arms B/C/D (the model-invoking arms) have not been run — the hybrid
comparison is pending.** Nothing in this repository reports fabricated
numbers.

## Dataset

Location: `datasets/main/` — `records.jsonl` (one labeled record per line)
plus `diffs/<id>.diff` sidecars. Managed exclusively through the
`guardian-bench` CLI:

```bash
guardian-bench fetch-osv --dataset benchmark/datasets/main --ecosystem pip --limit 20
guardian-bench validate  --dataset benchmark/datasets/main
guardian-bench stats     --dataset benchmark/datasets/main
```

### Record schema (v1)

| Field | Meaning |
|---|---|
| `category` | security · bug · auth_change · database_change · api_change · testing_deficiency · normal |
| `is_risky` | ground-truth label |
| `source` | `curated_osv` (advisory-backed) · `curated_dataset` · `mined` · `synthetic` |
| `direction` | `as_merged`, or `reversed_fix` — an advisory's fix commit applied backwards, i.e. the change that *introduces* the flaw |
| `label_status` | `confirmed` (historical evidence / human-verified) or `candidate` (heuristic). **Evaluation refuses candidates.** |
| `provenance` | source repo, commit SHA / PR, advisory + CWE ids, repo license, retrieval date |
| `expected_rules` | optional rule-level ground truth for finding-level metrics |

Splits are **not stored**: each record's calibration/holdout assignment
(≈70/30) is a deterministic hash of its id, so it cannot be reassigned after
looking at results. The holdout is untouched until the final evaluation run.

### Labeling protocol

1. `confirmed` requires historical evidence: a security advisory naming the
   fix commit (OSV/GHSA), a traced bug-introduction, a revert, or explicit
   human verification recorded in `notes`.
2. Mined records enter as `candidate` and are promoted only after human
   review.
3. Synthetic records are always marked `synthetic` and are reported
   separately from real-world results.
4. `guardian-bench validate` enforces: parseable diffs, no duplicates, no
   orphans, provenance on confirmed records. CI-friendly (exit 1 on any
   problem).

### Current seed batch (2026-08-15)

25 confirmed security records (15 PyPI + 10 npm ecosystems), each the
reverse of a GHSA/OSV advisory's fix commit — provenance, CWE ids, and repo
licenses recorded per item. Run `guardian-bench stats` for live composition.

Early observation worth preserving: several real reversed CVEs score LOW on
the deterministic arm (pattern rules don't cover their vulnerability
classes). That gap is the phenomenon the hybrid comparison is designed to
measure — not a reason to tune rules against the dataset (see protocol
rule on splits).

### Mined candidates (2026-08-16)

25 mined records from psf/requests and pallets/flask (merged ≥180 days ago —
survival is the low-risk evidence, deliberately **not** Guardian's own score,
which would make the false-positive rate circular). They span
normal/api/testing/database/auth categories and sit at `candidate` until
promoted via `guardian-bench confirm` — see
[datasets/main/REVIEW-CANDIDATES.md](datasets/main/REVIEW-CANDIDATES.md)
for the review sheet. Evaluation refuses them until then, so the FPR column
stays empty until review happens.

### Still to collect (target ≈200)

- ~40 bug records (SWE-bench / BugsInPy fix reversals)
- ~40 more mined auth/database/API/testing records
- ~40 more mined low-risk records
- Balance check across categories before freezing v1 of the dataset

## Evaluation

Four arms on identical inputs: **A** deterministic-only · **B** LLM-only ·
**C** hybrid (default) · **D** gated hybrid (`ai_escalation_gate=true`).

```bash
guardian-bench evaluate --dataset benchmark/datasets/main --arm A \
  --split calibration --output benchmark/results/<experiment-id>
```

Only CONFIRMED records are evaluated; a PR counts as flagged at risk ≥ 31
(the MEDIUM boundary, `--threshold` to vary). Each results directory holds
`experiment.json` (engine version, full config, model id, dataset
composition), `metrics.json` (with 95% Wilson intervals), and per-record
`outcomes.jsonl`/`outcomes.csv` — every published number is regenerable.
Metrics with empty denominators report `null`, never a fake 0 or 1.

### Real results so far

**Arm A (deterministic-only), calibration split (37 records: 20 risky, 17
benign), threshold 31 —
[results/2026-08-16-armA-calibration-50](results/2026-08-16-armA-calibration-50/):**

| Metric | Value | 95% CI |
|---|---|---|
| Recall | **0.15** (3/20) | [0.05, 0.36] |
| False-positive rate | **0.00** (0/17) | [0.00, 0.18] |
| Precision | 1.0 | [0.44, 1.0] |
| False-negative rate | 0.85 | [0.64, 0.95] |
| F1 | 0.26 | — |
| Mean latency / cost | ~4 ms / $0 | no model calls |

Reading: the deterministic arm is *precise but blind* — zero false alarms on
benign changes, but it catches only 3 of 20 real reversed CVEs. That is the
measured version of the usual static-analysis trade-off, and exactly the gap
arms B/C/D exist to close. Per protocol, rules are not tuned against these
records. (Earlier all-risky run preserved in
`results/2026-08-16-armA-calibration/`.)

Labeling disclosure: the 25 mined negatives were reviewed and confirmed by
Claude under delegation, recorded per record and in
[ADR-005](../docs/decisions/ADR-005-machine-labeling.md).

The holdout split remains untouched. Bedrock batch inference (50% cheaper)
is planned for the paid offline runs.
