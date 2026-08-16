# Candidate review sheet

Mined records awaiting human confirmation. For each: open the PR, sanity-check
the suggested category and the not-risky suggestion, then promote it:

```bash
guardian-bench confirm --dataset benchmark/datasets/main --id <id> --not-risky \
  --reviewed-by <you> --reason "<one line>"
```

Use `--risky` (and optionally `--category`) where the suggestion is wrong.

| Record | PR | Suggested category | Files | +/- |
|---|---|---|---:|---|
| `mined-psf-requests-pr8` | https://github.com/psf/requests/pull/8 | testing_deficiency | 2 | +9/-6 |
| `mined-psf-requests-pr10` | https://github.com/psf/requests/pull/10 | normal | 3 | +21/-4 |
| `mined-psf-requests-pr15` | https://github.com/psf/requests/pull/15 | testing_deficiency | 1 | +2/-2 |
| `mined-psf-requests-pr24` | https://github.com/psf/requests/pull/24 | normal | 1 | +10/-10 |
| `mined-psf-requests-pr25` | https://github.com/psf/requests/pull/25 | auth_change | 2 | +17/-12 |
| `mined-psf-requests-pr26` | https://github.com/psf/requests/pull/26 | testing_deficiency | 2 | +44/-14 |
| `mined-psf-requests-pr28` | https://github.com/psf/requests/pull/28 | normal | 2 | +9/-4 |
| `mined-psf-requests-pr29` | https://github.com/psf/requests/pull/29 | normal | 2 | +9/-7 |
| `mined-psf-requests-pr32` | https://github.com/psf/requests/pull/32 | database_change | 3 | +32/-19 |
| `mined-psf-requests-pr34` | https://github.com/psf/requests/pull/34 | database_change | 5 | +31/-25 |
| `mined-psf-requests-pr35` | https://github.com/psf/requests/pull/35 | api_change | 4 | +7/-36 |
| `mined-psf-requests-pr37` | https://github.com/psf/requests/pull/37 | database_change | 1 | +6/-0 |
| `mined-psf-requests-pr38` | https://github.com/psf/requests/pull/38 | api_change | 1 | +16/-12 |
| `mined-psf-requests-pr39` | https://github.com/psf/requests/pull/39 | normal | 1 | +1/-1 |
| `mined-psf-requests-pr45` | https://github.com/psf/requests/pull/45 | api_change | 1 | +16/-10 |
| `mined-pallets-flask-pr196` | https://github.com/pallets/flask/pull/196 | api_change | 5 | +20/-20 |
| `mined-pallets-flask-pr204` | https://github.com/pallets/flask/pull/204 | normal | 1 | +82/-47 |
| `mined-pallets-flask-pr228` | https://github.com/pallets/flask/pull/228 | normal | 1 | +5/-5 |
| `mined-pallets-flask-pr230` | https://github.com/pallets/flask/pull/230 | normal | 1 | +1/-1 |
| `mined-pallets-flask-pr232` | https://github.com/pallets/flask/pull/232 | testing_deficiency | 1 | +2/-1 |
| `mined-pallets-flask-pr236` | https://github.com/pallets/flask/pull/236 | testing_deficiency | 1 | +11/-0 |
| `mined-pallets-flask-pr237` | https://github.com/pallets/flask/pull/237 | testing_deficiency | 1 | +4/-1 |
| `mined-pallets-flask-pr238` | https://github.com/pallets/flask/pull/238 | normal | 1 | +3/-2 |
| `mined-pallets-flask-pr243` | https://github.com/pallets/flask/pull/243 | normal | 1 | +1/-1 |
| `mined-pallets-flask-pr249` | https://github.com/pallets/flask/pull/249 | normal | 1 | +7/-7 |
