"""Guardian CLI — local pull-request risk analysis (Week 1 milestone).

Examples:
    guardian analyze --diff pr.diff --meta pr.json
    guardian analyze --diff pr.diff --repo acme/shop --pr 42 --format json
    guardian analyze --diff pr.diff --fail-on HIGH   # CI gate: exit 1 at HIGH+
    guardian rules
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from guardian.analyzers.security import SecurityAnalyzer
from guardian.github.pr_loader import load_pr
from guardian.models.config import load_config
from guardian.models.report import RiskLevel
from guardian.reporting.markdown import render_markdown
from guardian.services.analysis_service import AnalysisService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardian", description="AI-SDLC Guardian — PR risk analysis")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze a pull-request diff")
    analyze.add_argument("--diff", required=True, help="Path to a unified diff file (git diff / GitHub .diff)")
    analyze.add_argument("--meta", help="Path to a JSON file with PR metadata")
    analyze.add_argument("--repo", dest="repository", help="Repository, e.g. acme/shop")
    analyze.add_argument("--pr", dest="pr_number", type=int, help="Pull request number")
    analyze.add_argument("--title", help="Pull request title")
    analyze.add_argument("--base", dest="base_sha", help="Base commit SHA")
    analyze.add_argument("--head", dest="head_sha", help="Head commit SHA")
    analyze.add_argument("--config", help="Path to a Guardian JSON config (weights, thresholds)")
    analyze.add_argument("--format", choices=("markdown", "json"), default="markdown")
    analyze.add_argument("--output", help="Write the report to this file instead of stdout")
    analyze.add_argument(
        "--fail-on",
        choices=("LOW", "MEDIUM", "HIGH", "CRITICAL"),
        help="Exit with status 1 if the risk level is at or above this (for CI gates)",
    )

    sub.add_parser("rules", help="List deterministic security rules")
    return parser


def _cmd_analyze(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    pr = load_pr(
        args.diff,
        args.meta,
        repository=args.repository,
        pr_number=args.pr_number,
        title=args.title,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )
    report = AnalysisService(config).analyze(pr)

    rendered = (
        report.model_dump_json(indent=2) if args.format == "json" else render_markdown(report)
    )
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    if args.fail_on and report.risk_level.rank >= RiskLevel(args.fail_on).rank:
        print(
            f"guardian: risk level {report.risk_level.value} >= --fail-on {args.fail_on}",
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_rules() -> int:
    print(f"{'RULE':<32} {'SEVERITY':<10} REASON")
    for rule, severity, reason in SecurityAnalyzer.rules():
        print(f"{rule:<32} {severity:<10} {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "analyze":
        return _cmd_analyze(args)
    if args.command == "rules":
        return _cmd_rules()
    return 2


if __name__ == "__main__":
    sys.exit(main())
