# ADR-005: Machine review of mined candidates

Date: 2026-08-16 · Status: accepted

## Decision

The 25 mined candidate records in the seed dataset were reviewed and
confirmed by **Claude (claude-opus-5), not a human**, under explicit
delegation from the project owner. Each record's notes name the reviewer and
a per-record justification; nothing about this is hidden in the data.

Review procedure: every candidate's full diff was read; the verdict
(risky/not-risky) rests on the survival evidence (merged ≥180 days —
in practice 14–15 years — into active repos, no traced advisory/revert/fix)
plus inspection finding no evident defect. Category suggestions from path
heuristics were corrected where wrong (e.g. `docs/api.rst` is documentation,
not an API change; `requests/models.py` is HTTP models, not database code).

## Rationale and consequences

- A named, disclosed machine labeler is methodologically weaker than a human
  labeler but stronger than unlabeled data or undisclosed provenance. The
  research write-up must state it plainly and treat it as a limitation.
- Inter-rater agreement with a human on a sample of these records is a
  cheap, worthwhile robustness check before the paper (open task).
- The labeling *protocol* is unchanged: candidates never enter evaluation;
  only confirmation with a named reviewer promotes them. This ADR documents
  who that reviewer was for the seed batch.
