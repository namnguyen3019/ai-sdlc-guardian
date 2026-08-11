"""Testing analyzer — flags production changes without corresponding tests."""

from __future__ import annotations

import re
from typing import ClassVar

from guardian.analyzers.base import BaseAnalyzer
from guardian.models.features import PRFeatures
from guardian.models.findings import Category, Finding, Severity
from guardian.models.pr import ChangeType, PRContext

_TEST_DEF = re.compile(r"^\s*(def test_|async def test_|it\(|test\(|describe\(|@Test\b)")


class TestingAnalyzer(BaseAnalyzer):
    __test__ = False  # tell pytest this is not a test class
    name: ClassVar[str] = "testing"

    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []
        test_paths = set(features.test_files)
        source_added = sum(
            f.additions for f in pr.files if f.path in set(features.source_files)
        )

        if features.test_files_changed == 0 and source_added >= self.config.untested_source_lines:
            severity = Severity.HIGH if source_added >= 3 * self.config.untested_source_lines else Severity.MEDIUM
            findings.append(
                Finding(
                    category=Category.TESTING,
                    severity=severity,
                    confidence=0.85,
                    rule="SOURCE_CHANGED_WITHOUT_TESTS",
                    reason=f"{source_added} lines of production code were added or "
                    f"modified across {features.source_files_changed} source file(s) "
                    "with no test files changed.",
                    recommendation="Add or update tests covering the changed behavior "
                    "before merging.",
                )
            )

        if features.auth_files and features.test_files_changed == 0:
            findings.append(
                Finding(
                    category=Category.TESTING,
                    severity=Severity.HIGH,
                    confidence=0.9,
                    file=features.auth_files[0],
                    rule="AUTH_CHANGE_WITHOUT_TESTS",
                    reason="Authentication behavior was modified but no tests were "
                    "added or updated.",
                    recommendation="Add authentication/authorization integration tests "
                    "covering the modified paths.",
                )
            )

        for change in pr.files:
            if change.path not in test_paths:
                continue
            if change.change_type == ChangeType.DELETED:
                findings.append(
                    Finding(
                        category=Category.TESTING,
                        severity=Severity.HIGH,
                        confidence=0.9,
                        file=change.path,
                        rule="TEST_FILE_DELETED",
                        reason="A test file was deleted.",
                        recommendation="Confirm the covered behavior was removed too, "
                        "or migrate the tests instead of deleting them.",
                    )
                )
                continue
            removed_tests = [
                line for line in change.removed_lines if _TEST_DEF.search(line.content)
            ]
            added_tests = [
                line for line in change.added_lines if _TEST_DEF.search(line.content)
            ]
            if len(removed_tests) > len(added_tests):
                findings.append(
                    Finding(
                        category=Category.TESTING,
                        severity=Severity.MEDIUM,
                        confidence=0.7,
                        file=change.path,
                        line=removed_tests[0].line_number,
                        rule="TEST_CASES_REMOVED",
                        reason=f"{len(removed_tests) - len(added_tests)} test case(s) "
                        "appear to have been removed from this file.",
                        recommendation="Verify the removed tests are obsolete rather "
                        "than inconvenient; replace coverage where behavior remains.",
                    )
                )
        return findings
