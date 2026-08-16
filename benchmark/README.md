# Benchmark framework

**Status: dataset collection in progress.** The pipeline (schema, fetcher,
validator, splits) is built and tested; a 25-record confirmed seed batch is
committed. **No evaluation has been run yet — all comparison results are
pending.** Nothing in this repository reports fabricated numbers.

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

### Still to collect (target ≈200)

- ~40 bug records (SWE-bench / BugsInPy fix reversals)
- ~50 mined auth/database/API/testing records (candidate → human-confirmed)
- ~50 mined low-risk records (merged, lines untouched ≥6 months)
- Balance check across categories before freezing v1 of the dataset

## Evaluation plan (next step)

Four arms on identical inputs: **A** deterministic-only · **B** LLM-only ·
**C** hybrid (default) · **D** gated hybrid (`ai_escalation_gate=true`).
Metrics: precision, recall, F1, FP/FN rate, latency, cost per analysis —
computed on the holdout only, reported with confidence intervals, exported
to JSON and CSV under `results/<experiment-id>/` together with the exact
engine version, config, and model id. Bedrock batch inference (50% cheaper)
for the offline runs.
