# Benchmark framework

**Status: pending (Week 4 deliverable). No results have been collected yet;
nothing here reports fabricated numbers.**

## Plan

Evaluate 100–300 labeled pull requests across categories: security
vulnerabilities, bugs, authentication changes, database changes, API changes,
testing deficiencies, and normal low-risk changes.

Three approaches are compared on identical inputs:

- **A — deterministic only** (Week 1 engine, AI weight = 0)
- **B — LLM only** (Bedrock analyzer alone)
- **C — Guardian hybrid** (default configuration)

Metrics: precision, recall, F1, false-positive rate, false-negative rate,
average latency, average cost per analysis. Results export to JSON and CSV.

## Layout

- `datasets/` — labeled PR diffs + ground-truth annotations
- `scripts/` — evaluation runners (deterministic seeds, pinned configs)
- `results/` — raw and aggregated outputs, one directory per experiment,
  each with the exact engine version, config, and model id used

Reproducibility rule: every published number must be regenerable from a
committed config + dataset revision.
