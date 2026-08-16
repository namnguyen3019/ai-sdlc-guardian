"""guardian-bench — dataset collection and validation.

    guardian-bench fetch-osv --dataset benchmark/datasets/main --limit 20
    guardian-bench validate  --dataset benchmark/datasets/main
    guardian-bench stats     --dataset benchmark/datasets/main
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request

from guardian.benchmark import mining, osv
from guardian.benchmark.dataset import (
    composition,
    existing_ids,
    load_records,
    save_record,
    update_record,
)
from guardian.benchmark.runner import DEFAULT_THRESHOLD, Arm, evaluate, save_results
from guardian.benchmark.schema import BenchmarkCategory, LabelStatus, Split
from guardian.benchmark.validate import validate_dataset
from guardian.github.client import GitHubClient
from guardian.models.env import config_from_env

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("guardian-bench")


def _github_token(args: argparse.Namespace) -> str:
    token = args.token or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("a GitHub token is required: pass --token or set GITHUB_TOKEN")
    return token


def _list_advisory_ids(token: str, ecosystem: str, pages: int) -> list[str]:
    """GHSA ids from GitHub's global advisory index (newest first)."""
    ids: list[str] = []
    url = f"https://api.github.com/advisories?ecosystem={ecosystem}&per_page=100&type=reviewed"
    for _ in range(pages):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "ai-sdlc-guardian-benchmark",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            ids.extend(str(item["ghsa_id"]) for item in json.loads(response.read().decode()))
            link = response.headers.get("Link", "")
        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part[part.find("<") + 1 : part.find(">")]
        if not next_url:
            break
        url = next_url
    return ids


def cmd_fetch_osv(args: argparse.Namespace) -> int:
    token = _github_token(args)
    github = GitHubClient(token)
    advisory_ids = _list_advisory_ids(token, args.ecosystem, pages=args.pages)
    logger.info("found %d %s advisories to consider", len(advisory_ids), args.ecosystem)

    collected = osv.collect_security_records(
        advisory_ids,
        github,
        limit=args.limit,
        skip_ids=existing_ids(args.dataset),
    )
    for record, diff_text in collected:
        save_record(args.dataset, record, diff_text)
    print(f"saved {len(collected)} new confirmed security records to {args.dataset}")
    return 0


def cmd_mine(args: argparse.Namespace) -> int:
    token = _github_token(args)
    collected = mining.collect_mined_records(
        GitHubClient(token),
        args.repo,
        limit=args.limit,
        skip_ids=existing_ids(args.dataset),
        min_age_days=args.min_age_days,
        max_pages=args.pages,
    )
    for record, diff_text in collected:
        save_record(args.dataset, record, diff_text)
    print(f"saved {len(collected)} CANDIDATE records from {args.repo} to {args.dataset}")
    print("promote after human review: guardian-bench confirm --dataset ... --id ... --reviewed-by ...")
    return 0


def cmd_confirm(args: argparse.Namespace) -> int:
    records = {r.id: r for r in load_records(args.dataset)}
    if args.id not in records:
        print(f"no record with id {args.id}", file=sys.stderr)
        return 1
    record = records[args.id]
    record.label_status = LabelStatus.CONFIRMED
    record.is_risky = args.risky
    if args.category:
        record.category = BenchmarkCategory(args.category)
    from datetime import date

    verdict = "risky" if args.risky else "not risky"
    record.notes = (record.notes + " " if record.notes else "") + (
        f"[confirmed {verdict} by {args.reviewed_by} on {date.today().isoformat()}"
        + (f": {args.reason}" if args.reason else "")
        + "]"
    )
    update_record(args.dataset, record)
    print(f"{record.id}: confirmed {verdict} (category {record.category.value}) by {args.reviewed_by}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    problems = validate_dataset(args.dataset)
    if problems:
        for problem in problems:
            print(f"INVALID: {problem}", file=sys.stderr)
        return 1
    records = load_records(args.dataset)
    print(f"OK: {len(records)} records valid")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    print(json.dumps(composition(load_records(args.dataset)), indent=2))
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    arm = Arm(args.arm)
    provider = None
    if arm.needs_provider:
        # Paid arms call Bedrock for every record — make that explicit.
        from guardian.bedrock.client import BedrockProvider

        config = config_from_env()
        if args.model:
            config.bedrock_model_id = args.model
        provider = BedrockProvider(config)
        logger.warning(
            "arm %s invokes Bedrock model %s per record — this incurs cost",
            arm.value, config.bedrock_model_id,
        )
    else:
        config = config_from_env()

    split = Split(args.split) if args.split != "all" else None
    results = evaluate(
        args.dataset,
        arm,
        provider=provider,
        split=split,
        threshold=args.threshold,
        limit=args.limit,
        base_config=config,
    )
    save_results(results, args.output)
    print(json.dumps(results["metrics"], indent=2))
    print(f"results written to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guardian-bench", description="Benchmark dataset tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-osv", help="Collect advisory-backed security records")
    fetch.add_argument("--dataset", required=True, help="Dataset directory")
    fetch.add_argument("--ecosystem", default="pip", help="Advisory ecosystem (pip, npm, maven, go, ...)")
    fetch.add_argument("--limit", type=int, default=20, help="Max new records to collect")
    fetch.add_argument("--pages", type=int, default=3, help="Advisory index pages to scan (100/page)")
    fetch.add_argument("--token", help="GitHub token (defaults to GITHUB_TOKEN env)")
    fetch.set_defaults(func=cmd_fetch_osv)

    mine = sub.add_parser("mine", help="Mine merged PRs into CANDIDATE records")
    mine.add_argument("--dataset", required=True)
    mine.add_argument("--repo", required=True, help="Repository to mine, e.g. psf/requests")
    mine.add_argument("--limit", type=int, default=15)
    mine.add_argument("--min-age-days", type=int, default=180,
                      help="Only PRs merged at least this long ago (survival evidence)")
    mine.add_argument("--pages", type=int, default=3, help="PR list pages to scan (100/page, oldest first)")
    mine.add_argument("--token", help="GitHub token (defaults to GITHUB_TOKEN env)")
    mine.set_defaults(func=cmd_mine)

    confirm = sub.add_parser("confirm", help="Promote a CANDIDATE record after human review")
    confirm.add_argument("--dataset", required=True)
    confirm.add_argument("--id", required=True, help="Record id to confirm")
    confirm.add_argument("--reviewed-by", required=True, help="Who reviewed this record")
    risky_group = confirm.add_mutually_exclusive_group(required=True)
    risky_group.add_argument("--risky", action="store_true", dest="risky")
    risky_group.add_argument("--not-risky", action="store_false", dest="risky")
    confirm.add_argument("--category", choices=[c.value for c in BenchmarkCategory],
                         help="Override the suggested category")
    confirm.add_argument("--reason", help="Short justification recorded in the record notes")
    confirm.set_defaults(func=cmd_confirm)

    validate = sub.add_parser("validate", help="Validate a dataset directory")
    validate.add_argument("--dataset", required=True)
    validate.set_defaults(func=cmd_validate)

    stats = sub.add_parser("stats", help="Print dataset composition")
    stats.add_argument("--dataset", required=True)
    stats.set_defaults(func=cmd_stats)

    evaluate_parser = sub.add_parser("evaluate", help="Run one benchmark arm over the dataset")
    evaluate_parser.add_argument("--dataset", required=True)
    evaluate_parser.add_argument("--arm", required=True, choices=[a.value for a in Arm],
                                 help="A=deterministic, B=LLM-only, C=hybrid, D=gated hybrid")
    evaluate_parser.add_argument("--output", required=True, help="Results directory")
    evaluate_parser.add_argument("--split", default="calibration",
                                 choices=["calibration", "holdout", "all"],
                                 help="holdout is reserved for the final run")
    evaluate_parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                                 help="Risk score at/above which a PR counts as flagged")
    evaluate_parser.add_argument("--limit", type=int, help="Evaluate at most N records (smoke runs)")
    evaluate_parser.add_argument("--model", help="Override Bedrock model id (arms B/C/D)")
    evaluate_parser.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
