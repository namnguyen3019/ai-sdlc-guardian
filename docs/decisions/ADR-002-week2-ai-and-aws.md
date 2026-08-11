# ADR-002: Week 2 — AI analysis and AWS workflow

Date: 2026-08-11 · Status: accepted

## Decisions

1. **Provider abstraction over direct boto3.** The analysis layer depends on
   a minimal `LLMProvider` interface; `BedrockProvider` (Converse API) is one
   implementation, `StubProvider` powers offline tests, and an Ollama or
   Claude-Platform provider can be added without touching analyzers
   (development rule 15: no vendor lock-in in core interfaces).
2. **Evidence grounding is enforced in code, not requested in the prompt.**
   The parser drops any AI finding whose quoted evidence does not occur
   (whitespace-normalized) in the diff that was sent. This is the concrete
   mechanism behind "the AI must not claim code exists when it is not
   present". Rejected counts are reported and published as a metric.
3. **Prompt-injection defense.** The system prompt is static (cacheable) and
   instructs that diff content between `<untrusted_diff>` markers is data,
   never instructions; injection attempts are themselves findings. PR title
   and description are attacker-controlled and are not placed in the trusted
   sections at all.
4. **Two-Lambda Step Functions workflow** (analyze → store), not one Lambda
   per analyzer. Deterministic analyzers are pure functions finishing in
   milliseconds; distributing them would add latency, cost, and failure
   modes for nothing. The state machine keeps per-stage retries, timeouts,
   catch-to-fail, tracing, and logs required by the spec.
5. **Escalation gate ships but defaults off.** `ai_escalation_gate=true`
   skips Bedrock on clearly low-risk PRs (low deterministic score, small
   churn, no critical modules). Off by default so default scoring semantics
   match the specified architecture; it doubles as a benchmark arm
   ("gated hybrid") in Week 4.
6. **Metrics are low-cardinality by design.** No per-repository dimensions —
   each dimension combination bills as a separate CloudWatch metric.
   Per-repository analytics live in DynamoDB (`byRepository` GSI).
7. **DynamoDB stores no float and no content.** Costs are stored as integer
   micro-USD; findings text and diff content never enter the table. Full
   reports (with ≤300-char evidence excerpts) go to S3 only.
8. **Lambda bundling works without Docker.** Host pip cross-installs
   `manylinux2014_aarch64` wheels (pydantic-core is platform-specific);
   Docker bundling remains the automatic fallback.
9. **Week 1 CDK fixes.** Removed the hardcoded table name (collision on
   second deploy), added noncurrent-version expiry to the versioned report
   bucket, made point-in-time recovery a stack prop.

## Consequences

- A Bedrock outage degrades an analysis to deterministic-only (recorded in
  `analyzer_failures`, AI weight renormalized away) instead of failing it.
- The AI dimension can be silenced (`ai_enabled=false`) or gated without
  code changes, which is exactly the knob set the Week 4 benchmark needs.
- Deploys require either host `pip` + `python3` or a running Docker daemon.
