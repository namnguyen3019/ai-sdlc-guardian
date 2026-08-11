"""Complexity analyzer — size, churn, nesting, and error-handling signals."""

from __future__ import annotations

import re
from typing import ClassVar

from guardian.analyzers import paths
from guardian.analyzers.base import BaseAnalyzer
from guardian.models.features import PRFeatures
from guardian.models.findings import Category, Finding, Severity
from guardian.models.pr import ChangeType, PRContext

_EXCEPT_LINE = re.compile(r"^\s*(except\b|catch\b|catch\s*\(|rescue\b)")
_BARE_EXCEPT_PASS = re.compile(r"^\s*except\s*(Exception\s*)?:\s*(#.*)?$")
_DEEP_INDENT = re.compile(r"^(\t{5,}|[ ]{20,})\S")
_HIGH_CHURN_FILE_LINES = 300


class ComplexityAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "complexity"

    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []
        churn = features.total_churn

        if churn >= self.config.large_pr_lines:
            severity = (
                Severity.HIGH if churn >= self.config.very_large_pr_lines else Severity.MEDIUM
            )
            findings.append(
                Finding(
                    category=Category.COMPLEXITY,
                    severity=severity,
                    confidence=0.9,
                    rule="LARGE_PR",
                    reason=f"This PR changes {churn} lines "
                    f"({features.lines_added} added, {features.lines_deleted} deleted); "
                    "large changes are harder to review and correlate with defects.",
                    recommendation="Split the change into smaller, independently "
                    "reviewable PRs where possible.",
                )
            )

        if features.files_changed >= self.config.large_pr_files:
            findings.append(
                Finding(
                    category=Category.COMPLEXITY,
                    severity=Severity.MEDIUM,
                    confidence=0.85,
                    rule="MANY_FILES_CHANGED",
                    reason=f"{features.files_changed} files are changed in a single PR.",
                    recommendation="Group unrelated changes into separate PRs.",
                )
            )

        for change in pr.files:
            if change.is_binary or not paths.is_source_file(change.path):
                continue
            findings.extend(self._per_file_findings(change))
        return findings

    def _per_file_findings(self, change) -> list[Finding]:
        findings: list[Finding] = []

        file_churn = change.additions + change.deletions
        if file_churn >= _HIGH_CHURN_FILE_LINES and change.change_type == ChangeType.MODIFIED:
            findings.append(
                Finding(
                    category=Category.COMPLEXITY,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    file=change.path,
                    rule="HIGH_CHURN_FILE",
                    reason=f"{file_churn} lines changed in one existing file; large "
                    "single-file rewrites are risky to review.",
                    recommendation="Consider splitting the refactor from behavior "
                    "changes.",
                )
            )

        deep = next((l for l in change.added_lines if _DEEP_INDENT.match(l.content)), None)
        if deep is not None:
            findings.append(
                Finding(
                    category=Category.COMPLEXITY,
                    severity=Severity.LOW,
                    confidence=0.6,
                    file=change.path,
                    line=deep.line_number,
                    rule="DEEP_NESTING",
                    reason="Added code is nested five or more levels deep.",
                    recommendation="Extract helper functions or use early returns to "
                    "flatten control flow.",
                )
            )

        removed_handlers = [l for l in change.removed_lines if _EXCEPT_LINE.match(l.content)]
        added_handlers = [l for l in change.added_lines if _EXCEPT_LINE.match(l.content)]
        if len(removed_handlers) > len(added_handlers):
            findings.append(
                Finding(
                    category=Category.COMPLEXITY,
                    severity=Severity.HIGH,
                    confidence=0.75,
                    file=change.path,
                    line=removed_handlers[0].line_number,
                    rule="EXCEPTION_HANDLING_REMOVED",
                    reason="Exception handling was removed without an added "
                    "replacement in this file.",
                    recommendation="Confirm errors are still handled or intentionally "
                    "propagated; document the new failure behavior.",
                )
            )

        swallowed = next(
            (l for l in change.added_lines if _BARE_EXCEPT_PASS.match(l.content)), None
        )
        if swallowed is not None:
            findings.append(
                Finding(
                    category=Category.COMPLEXITY,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    file=change.path,
                    line=swallowed.line_number,
                    rule="BROAD_EXCEPTION_HANDLER",
                    reason="A broad/bare exception handler was added, which can "
                    "silently swallow errors.",
                    recommendation="Catch specific exceptions and log or re-raise "
                    "unexpected ones.",
                )
            )
        return findings
