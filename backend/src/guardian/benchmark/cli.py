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

from guardian.benchmark import osv
from guardian.benchmark.dataset import composition, existing_ids, load_records, save_record
from guardian.benchmark.validate import validate_dataset
from guardian.github.client import GitHubClient

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

    validate = sub.add_parser("validate", help="Validate a dataset directory")
    validate.add_argument("--dataset", required=True)
    validate.set_defaults(func=cmd_validate)

    stats = sub.add_parser("stats", help="Print dataset composition")
    stats.add_argument("--dataset", required=True)
    stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
