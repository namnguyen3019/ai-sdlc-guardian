"""Dependency analyzer — manifest and lockfile changes."""

from __future__ import annotations

import re
from typing import ClassVar

from guardian.analyzers import paths
from guardian.analyzers.base import BaseAnalyzer
from guardian.models.features import PRFeatures
from guardian.models.findings import Category, Finding, Severity
from guardian.models.pr import PRContext

_UNPINNED = re.compile(
    r"""^\s*[\w.\[\]-]+\s*(>=[^,<]+$|>\s*[\d.]+\s*$)|["'][^"']+["']\s*:\s*["'](\*|latest)["']""",
)
_PKG_NAME = re.compile(r"^\s*\+?\s*([A-Za-z0-9_.\[\]-]+)")


class DependencyAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "dependency"

    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []
        manifest_changed = False

        for change in pr.files:
            if paths.is_dependency_manifest(change.path):
                manifest_changed = True
                findings.append(
                    Finding(
                        category=Category.DEPENDENCY,
                        severity=Severity.MEDIUM,
                        confidence=0.85,
                        file=change.path,
                        rule="DEPENDENCY_MANIFEST_CHANGED",
                        reason="A dependency manifest was changed; new or upgraded "
                        "third-party code will run with this service's privileges.",
                        recommendation="Review changelogs/advisories for each changed "
                        "dependency and prefer pinned versions.",
                    )
                )
                findings.extend(self._manifest_line_findings(change))

        lockfiles = [f.path for f in pr.files if paths.is_lockfile(f.path)]
        if lockfiles and not manifest_changed:
            findings.append(
                Finding(
                    category=Category.DEPENDENCY,
                    severity=Severity.LOW,
                    confidence=0.6,
                    file=lockfiles[0],
                    rule="LOCKFILE_ONLY_CHANGE",
                    reason="A lockfile changed without a manifest change — transitive "
                    "dependency versions moved.",
                    recommendation="Confirm the lockfile regeneration was intentional.",
                )
            )
        return findings

    def _manifest_line_findings(self, change) -> list[Finding]:
        findings: list[Finding] = []
        removed_names = {
            m.group(1).lower()
            for l in change.removed_lines
            if (m := _PKG_NAME.match(l.content)) is not None
        }
        new_deps = []
        for line in change.added_lines:
            m = _PKG_NAME.match(line.content)
            if m and m.group(1).lower() not in removed_names and not line.content.strip().startswith(("#", "//")):
                new_deps.append((m.group(1), line))
        # Only report a sample to avoid drowning the report on big manifests.
        for name, line in new_deps[:5]:
            findings.append(
                Finding(
                    category=Category.DEPENDENCY,
                    severity=Severity.MEDIUM,
                    confidence=0.55,
                    file=change.path,
                    line=line.line_number,
                    rule="NEW_DEPENDENCY_ADDED",
                    reason=f"Dependency entry '{name}' appears to be newly added.",
                    recommendation="Vet the package (maintenance, popularity, known "
                    "CVEs) before adopting it.",
                    evidence=line.content.strip()[:200],
                )
            )
        for line in change.added_lines:
            if _UNPINNED.search(line.content):
                findings.append(
                    Finding(
                        category=Category.DEPENDENCY,
                        severity=Severity.MEDIUM,
                        confidence=0.6,
                        file=change.path,
                        line=line.line_number,
                        rule="UNPINNED_DEPENDENCY_VERSION",
                        reason="A dependency version is unpinned or unbounded, so "
                        "future installs may pull untested versions.",
                        recommendation="Pin an exact version or a bounded range and "
                        "rely on a lockfile.",
                        evidence=line.content.strip()[:200],
                    )
                )
                break  # one finding per manifest is enough
        return findings
