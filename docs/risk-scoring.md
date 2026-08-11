# Risk scoring methodology

## Goals

1. **Explainable** — every point in the score traces to named findings.
2. **Deterministic** — same findings, same score; the LLM never emits the
   final number.
3. **Configurable** — weights and severity points are configuration, not code.

## From findings to dimension scores

Each finding carries a severity and a confidence (0–1). A scoring *dimension*
(security, testing, change_impact, complexity, ai_risk) receives:

```
dimension_score = min(100, round( Σ points(severity) × confidence ))

points: LOW = 6, MEDIUM = 14, HIGH = 28, CRITICAL = 45   (configurable)
```

Properties: one confident CRITICAL finding alone (45) puts a dimension near
the middle of the scale; two push it toward saturation; low-confidence noise
contributes proportionally little. The cap keeps a flood of findings from
overflowing the scale.

Finding categories map to dimensions; `dependency` findings roll into
`change_impact` (dependency changes are an impact concern for the composite
score, while keeping their own category label in the report).

## From dimensions to the overall score

```
overall = round( Σ weight(d) × dimension_score(d) )
```

Default weights: security 0.30, testing 0.25, change impact 0.20,
complexity 0.15, AI 0.10. When a signal *source* is unavailable (e.g. AI
analysis disabled in Week 1), its weight is removed and the remaining weights
are renormalized — an unavailable analyzer must not deflate risk.

## Risk levels and merge recommendations

| Score | Level | Recommendation |
|---|---|---|
| 0–30 | LOW | APPROVE |
| 31–60 | MEDIUM | REVIEW RECOMMENDED |
| 61–80 | HIGH | REVIEW REQUIRED |
| 81–100 | CRITICAL | BLOCK |

The level boundaries are fixed product semantics and deliberately not
configurable.

## Explainability contract

The report carries, per dimension: the score, the effective weight, the
weighted contribution, and a sentence naming the severity mix and the most
severe finding (`rule` + location). Every finding in turn carries `reason`,
`recommendation`, and (where applicable) `evidence` quoted from the diff.

## Week 2: the AI dimension

The Bedrock analyzer returns structured findings in the same schema
(category `ai`). Requirements: findings must cite evidence present in the
supplied diff; findings without evidence are discarded; severity/confidence
from the model are inputs to the same formula above. This keeps the hybrid
score grounded and the deterministic/AI contributions separable for the
benchmark (approaches A, B, C).
