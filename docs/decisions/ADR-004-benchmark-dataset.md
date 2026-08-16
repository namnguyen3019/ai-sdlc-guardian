# ADR-004: Benchmark dataset design

Date: 2026-08-15 · Status: accepted

## Decisions

1. **Reverse-diff labeling.** Security ground truth comes from OSV/GHSA
   advisories: the advisory's fix commit applied backwards is a change that
   *introduces* a confirmed vulnerability. Every such record is born
   CONFIRMED with the advisory id, CWE ids, commit SHA, and repo license in
   provenance. (GHSA-sourced OSV records link fix commits as WEB references,
   not FIX — the parser accepts both, preferring FIX.)
2. **Deterministic, unstored splits.** Calibration/holdout (≈70/30) is
   `sha256(record_id)` — a pure function, recomputed on read. Nobody can
   quietly move a record between splits, and the assignment survives
   re-fetches and machines identically.
3. **Two-tier labels.** `confirmed` (historical evidence or human-verified)
   vs `candidate` (heuristic). `evaluation_ready()` filters to confirmed;
   the validator and the future runner both refuse candidates, so heuristic
   labels can never leak into published numbers.
4. **Dataset code lives in the package** (`guardian.benchmark`), thin CLI in
   `guardian-bench`. Keeps the collection logic under the same test/coverage
   discipline as the engine (148 tests currently), with `benchmark/` holding
   only data and docs.
5. **Size cap per record** (2,000 diff lines): benchmark items must be
   reviewable; giant vendored-code fixes measure nothing about review risk.
6. **No tuning on observed misses.** The seed batch already shows real CVEs
   the deterministic rules score LOW. Rules may evolve for product reasons,
   but never by fitting to dataset records — the calibration/holdout
   discipline exists precisely so the paper's numbers survive scrutiny.

## Consequences

- Every committed record is reproducible from public sources; the dataset
  can be regenerated (or audited) from `records.jsonl` provenance alone.
- Diffs of open-source code are redistributed with license ids recorded per
  record; only diffs are stored, never full sources — consistent with the
  project's data-minimization stance.
- The 30% holdout stays untouched until the final Week 4 evaluation run.
