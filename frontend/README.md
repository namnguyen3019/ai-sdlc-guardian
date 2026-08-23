# Guardian dashboard

React + TypeScript + Vite dashboard for AI-SDLC Guardian. Deliberately small —
the analysis engine is the product. No chart library: bars and the trend line
are inline SVG/CSS, so there are no external asset or CSP concerns.

## Views

- Summary cards: PRs analyzed, average risk, total findings
- Risk-level distribution (LOW/MEDIUM/HIGH/CRITICAL)
- Findings by severity
- Mean score per dimension (security/testing/change-impact/complexity/AI)
- Risk trend over time (gridlines at the 30/60/80 level boundaries)
- Recent analyses table

## Run

```bash
cd frontend
npm install
npm run gen-data     # writes public/data.json from real Guardian runs
npm run dev          # http://localhost:5173
```

`npm run build` type-checks and produces a static `dist/` (deployable to S3 +
CloudFront, or any static host).

## Data source

The dashboard fetches `./data.json` at runtime and never talks to AWS
directly. Two ways to produce it, both via `guardian.dashboard`:

- **Sample (default):** `npm run gen-data` runs the deterministic engine over
  the benchmark diffs and summarizes the results — every number is genuine
  Guardian output (currently the deterministic arm only, so most PRs read
  LOW; that reflects the measured arm-A baseline, not a bug).
- **Live:** scan the DynamoDB analyses table and pass the items through
  `guardian.dashboard.from_dynamodb_items(items)`, writing the result to
  `public/data.json` (or serve it from a small read-only API / scheduled
  export). The item shape matches what the store Lambda writes.
