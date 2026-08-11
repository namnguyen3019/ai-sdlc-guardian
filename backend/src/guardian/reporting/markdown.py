"""Markdown report renderer — the same format is posted as the GitHub PR
comment in Week 3, marked so the comment can be found and updated in place."""

from __future__ import annotations

from guardian.models.findings import Finding, Severity
from guardian.models.report import RiskReport

GUARDIAN_COMMENT_MARKER = "<!-- ai-sdlc-guardian-report -->"

_LEVEL_EMOJI = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}


def _finding_block(index: int, finding: Finding) -> str:
    location = finding.file or "(PR-wide)"
    if finding.line:
        location += f":{finding.line}"
    lines = [
        f"**{index}. [{finding.severity.value}] {finding.rule}** — `{location}`",
        "",
        finding.reason,
        "",
        f"*Recommendation:* {finding.recommendation}",
    ]
    if finding.evidence:
        lines += ["", f"*Evidence:* `{finding.evidence}`"]
    lines += ["", f"*Confidence: {finding.confidence:.0%} · Source: {finding.source.value}*"]
    return "\n".join(lines)


def render_markdown(report: RiskReport) -> str:
    emoji = _LEVEL_EMOJI[report.risk_level.value]
    out: list[str] = [
        GUARDIAN_COMMENT_MARKER,
        "## 🛡️ AI-SDLC Guardian",
        "",
        f"**Overall Risk: {report.overall_risk}/100 — {emoji} {report.risk_level.value}**",
        "",
        "| Dimension | Score | Weight |",
        "|---|---:|---:|",
    ]
    for explanation in report.explanations:
        label = explanation.dimension.replace("_", " ").title()
        out.append(f"| {label} | {explanation.score}/100 | {explanation.weight:.0%} |")

    important = [f for f in report.findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
    if important:
        out += ["", f"### Key findings ({len(important)})", ""]
        for i, finding in enumerate(important[:10], start=1):
            out += [_finding_block(i, finding), ""]
        if len(important) > 10:
            out.append(f"*…and {len(important) - 10} more high-severity findings.*")

    remaining = [f for f in report.findings if f.severity not in (Severity.CRITICAL, Severity.HIGH)]
    if remaining:
        out += ["", "<details>", f"<summary>All other findings ({len(remaining)})</summary>", ""]
        for i, finding in enumerate(remaining, start=1):
            out += [_finding_block(i, finding), ""]
        out += ["</details>"]

    out += ["", "### Why this score", ""]
    for explanation in report.explanations:
        label = explanation.dimension.replace("_", " ").title()
        out.append(
            f"- **{label}** ({explanation.score}/100 × {explanation.weight:.0%} = "
            f"{explanation.weighted_contribution} points): {explanation.detail}"
        )

    out += ["", f"### Merge recommendation: **{report.merge_recommendation.value}**"]

    if report.analyzer_failures:
        out += ["", "> ⚠️ Some analyzers failed and were skipped: "
                + ", ".join(f.analyzer for f in report.analyzer_failures)]

    out += [
        "",
        "---",
        f"*Analysis `{report.analysis_id}` · engine v{report.engine_version} · "
        f"{report.features.files_changed} files, +{report.features.lines_added}/-{report.features.lines_deleted} · "
        f"{report.duration_ms} ms*",
    ]
    return "\n".join(out)
