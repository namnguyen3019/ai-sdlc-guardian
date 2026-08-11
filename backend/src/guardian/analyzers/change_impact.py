"""Change-impact analyzer — what parts of the system does this PR touch?"""

from __future__ import annotations

import re
from typing import ClassVar

from guardian.analyzers import paths
from guardian.analyzers.base import BaseAnalyzer
from guardian.models.features import PRFeatures
from guardian.models.findings import Category, Finding, Severity
from guardian.models.pr import ChangeType, PRContext

_PUBLIC_ENDPOINT = re.compile(
    r"^\s*(@(app|router|api)\.(get|post|put|patch|delete|route)\b|def\s+\w+|router\.(get|post|put|patch|delete)\b|app\.(get|post|put|patch|delete)\b)"
)


class ChangeImpactAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "change_impact"

    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []

        for path in features.critical_files:
            findings.append(
                Finding(
                    category=Category.CHANGE_IMPACT,
                    severity=Severity.HIGH,
                    confidence=0.8,
                    file=path,
                    rule="CRITICAL_MODULE_MODIFIED",
                    reason="A critical module (auth, payment, or data layer) was "
                    "modified.",
                    recommendation="Route this PR to an owner of the affected module "
                    "and verify rollback is possible.",
                )
            )

        for path in features.database_files:
            findings.append(
                Finding(
                    category=Category.CHANGE_IMPACT,
                    severity=Severity.HIGH,
                    confidence=0.85,
                    file=path,
                    rule="DATABASE_SCHEMA_CHANGED",
                    reason="Database schema, migration, or SQL was changed.",
                    recommendation="Verify the migration is backward-compatible, "
                    "reversible, and safe to run against production data volumes.",
                )
            )

        for path in features.config_files:
            findings.append(
                Finding(
                    category=Category.CHANGE_IMPACT,
                    severity=Severity.LOW,
                    confidence=0.6,
                    file=path,
                    rule="CONFIGURATION_CHANGED",
                    reason="A configuration file was changed.",
                    recommendation="Confirm the change is intended for every "
                    "environment that consumes this file.",
                )
            )

        for path in features.ci_files:
            findings.append(
                Finding(
                    category=Category.CHANGE_IMPACT,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    file=path,
                    rule="CI_PIPELINE_CHANGED",
                    reason="A CI/CD pipeline definition was changed.",
                    recommendation="Have someone with pipeline ownership review; "
                    "pipeline changes can affect every future merge.",
                )
            )

        for path in features.infra_files:
            findings.append(
                Finding(
                    category=Category.CHANGE_IMPACT,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    file=path,
                    rule="INFRASTRUCTURE_CHANGED",
                    reason="Infrastructure-as-code or container definition was changed.",
                    recommendation="Review the planned resource diff before deploying.",
                )
            )

        for path in features.deleted_files:
            if paths.is_source_file(path):
                findings.append(
                    Finding(
                        category=Category.CHANGE_IMPACT,
                        severity=Severity.MEDIUM,
                        confidence=0.7,
                        file=path,
                        rule="SOURCE_FILE_DELETED",
                        reason="A source file was deleted.",
                        recommendation="Confirm nothing imports or depends on the "
                        "deleted module.",
                    )
                )

        findings.extend(self._api_surface_findings(pr, features))
        return findings

    def _api_surface_findings(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []
        api_paths = set(features.api_files)
        for change in pr.files:
            if change.path not in api_paths or change.change_type == ChangeType.ADDED:
                continue
            removed = [l for l in change.removed_lines if _PUBLIC_ENDPOINT.match(l.content)]
            added = [l for l in change.added_lines if _PUBLIC_ENDPOINT.match(l.content)]
            if len(removed) > len(added):
                findings.append(
                    Finding(
                        category=Category.CHANGE_IMPACT,
                        severity=Severity.HIGH,
                        confidence=0.65,
                        file=change.path,
                        line=removed[0].line_number,
                        rule="API_CONTRACT_CHANGED",
                        reason="Public API handlers/definitions appear to be removed "
                        "or renamed — a potential breaking change for clients.",
                        recommendation="Version the API or provide a deprecation path "
                        "before removing endpoints.",
                    )
                )
        return findings
