# Contributing to AI-SDLC Guardian

Thanks for helping! Guardian aims to be a credible, reproducible research
platform — correctness and explainability beat cleverness.

## Development setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=guardian
```

Infrastructure:

```bash
cd infrastructure && npm install && npm run build
```

## Ground rules

- **Tests with every change.** Core analysis components stay at ≥80%
  coverage (currently ~98%).
- **Explainable findings.** Every rule must emit a `reason` and an actionable
  `recommendation`; line-level rules should attach `evidence`.
- **Repository code is untrusted input.** Analyzer code must never execute,
  import, or eval diff content, and never treat it as instructions.
- **No fabricated data.** Benchmark numbers only from real runs; unknown =
  "pending".
- **Small PRs**, conventional-commit style messages (`feat(analyzers): …`).

## Adding an analyzer rule

1. Add the rule (data-driven where possible — see
   `guardian/analyzers/security.py::LINE_RULES`).
2. Add positive *and* negative test cases (the false-positive test matters
   most).
3. Document the rule id in your PR description.

## Reporting security issues

Please do not open public issues for vulnerabilities — see
[SECURITY.md](SECURITY.md).
