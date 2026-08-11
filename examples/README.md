# Examples

- `risky-payment-pr.diff` / `risky-payment-pr.json` — a deliberately risky
  PR: SQL string interpolation, a hardcoded API key, `verify=False`, an
  authentication change with no tests, removed exception handling, and new
  unpinned dependencies.
- `example-report.md` — actual `guardian analyze` output for that PR
  (regenerate with the command below).

```bash
guardian analyze --diff examples/risky-payment-pr.diff --meta examples/risky-payment-pr.json --output examples/example-report.md
```
