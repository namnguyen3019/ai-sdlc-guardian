# ADR-001: Week 1 foundations

Date: 2026-08-11 · Status: accepted

## Decisions

1. **Single installable package `guardian` under `backend/src/`** (rather
   than bare top-level packages like `src/analyzers`). Gives clean imports
   (`guardian.analyzers`), an entry point (`guardian` CLI), and avoids a
   future name collision between our `github` module and the PyGithub
   package. This is the only deviation from the reference repo layout.
2. **Findings-only scoring.** All risk signal flows through `Finding`
   objects; the scoring engine knows nothing about analyzers. Rationale:
   analyzers stay independently testable and the AI analyzer plugs in without
   touching scoring (development rules 9, 12).
3. **Weight renormalization over absent sources.** With AI analysis absent in
   Week 1, its 10% weight is redistributed instead of zero-filling, so Week 1
   scores are comparable to hybrid scores later.
4. **stdlib `argparse` + JSON config, no YAML/click dependency.** Runtime
   dependency surface is exactly `pydantic` (development rule: keep the MVP
   simple, avoid lock-in).
5. **Diff-only analysis.** Guardian analyzes the unified diff plus metadata;
   it never checks out or stores the repository (privacy + cost).
6. **MIT license.**

## Consequences

- Lambda handlers (Week 2) will vendor the same package; no code moves.
- Regex-based rules trade recall for zero-execution safety on untrusted
  input; deeper semantic checks belong to the Bedrock analyzer (Week 2) and
  are benchmarked against this baseline (Week 4).
