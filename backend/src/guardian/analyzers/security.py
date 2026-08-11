"""Rule-based security analyzer.

Scans *added* lines of the diff with data-driven regex rules, plus path-level
rules for sensitive modules. Diff content is treated strictly as data — it is
matched, never evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from guardian.analyzers import paths
from guardian.analyzers.base import BaseAnalyzer
from guardian.models.features import PRFeatures
from guardian.models.findings import Category, Finding, Severity
from guardian.models.pr import ChangeType, PRContext

_COMMENT_PREFIXES = ("#", "//", "*", "--", "/*")


@dataclass(frozen=True)
class RegexRule:
    rule: str
    pattern: re.Pattern
    severity: Severity
    confidence: float
    reason: str
    recommendation: str
    skip_comments: bool = True


LINE_RULES: tuple[RegexRule, ...] = (
    RegexRule(
        rule="SQL_INJECTION_RISK",
        pattern=re.compile(
            r"""(f["'][^"']*\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b[^"']*\{)"""
            r"""|(["'][^"']*\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b[^"']*["']\s*(%|\+)\s*\w)"""
            r"""|(\b(execute|executemany|raw|query)\s*\(\s*f["'])""",
            re.IGNORECASE,
        ),
        severity=Severity.CRITICAL,
        confidence=0.85,
        reason="SQL appears to be built from string interpolation or concatenation, "
        "which allows user-controlled input to reach the query text.",
        recommendation="Use parameterized queries / prepared statements instead of "
        "interpolating values into SQL.",
    ),
    RegexRule(
        rule="HARDCODED_SECRET",
        pattern=re.compile(
            r"""(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|private[_-]?key)\b\s*[:=]\s*["'][^"']{6,}["']""",
        ),
        severity=Severity.CRITICAL,
        confidence=0.7,
        reason="A credential-like value appears to be hardcoded in source.",
        recommendation="Move secrets to a secrets manager or environment variable and "
        "rotate any value that was committed.",
        skip_comments=False,
    ),
    RegexRule(
        rule="CODE_INJECTION_RISK",
        pattern=re.compile(r"\b(eval|exec)\s*\(|new\s+Function\s*\("),
        severity=Severity.HIGH,
        confidence=0.7,
        reason="Dynamic code execution (eval/exec/new Function) was introduced.",
        recommendation="Avoid dynamic code execution; use explicit dispatch or safe "
        "parsers for the input being handled.",
    ),
    RegexRule(
        rule="SHELL_INJECTION_RISK",
        pattern=re.compile(r"shell\s*=\s*True|os\.system\s*\(|child_process\.exec\s*\("),
        severity=Severity.HIGH,
        confidence=0.75,
        reason="A shell command is executed in a way that can allow command injection.",
        recommendation="Use argument-vector process APIs (subprocess.run with a list, "
        "execFile) and never pass user input to a shell string.",
    ),
    RegexRule(
        rule="UNSAFE_DESERIALIZATION",
        pattern=re.compile(r"pickle\.loads?\s*\(|marshal\.loads?\s*\(|yaml\.load\s*\((?!.*SafeLoader)"),
        severity=Severity.HIGH,
        confidence=0.8,
        reason="Unsafe deserialization of potentially untrusted data was introduced.",
        recommendation="Use a safe format (JSON) or safe loader (yaml.safe_load); never "
        "unpickle untrusted input.",
    ),
    RegexRule(
        rule="WEAK_CRYPTO",
        pattern=re.compile(r"\b(md5|sha1)\s*\(|MessageDigest\.getInstance\(\s*[\"'](MD5|SHA-?1)|\bDES\b|\bECB\b"),
        severity=Severity.MEDIUM,
        confidence=0.6,
        reason="A weak cryptographic primitive (MD5/SHA-1/DES/ECB) was introduced.",
        recommendation="Use a modern primitive (SHA-256+, AES-GCM) or a vetted "
        "password-hashing function (bcrypt/argon2) for credentials.",
    ),
    RegexRule(
        rule="TLS_VERIFICATION_DISABLED",
        pattern=re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true|CURLOPT_SSL_VERIFYPEER,\s*0"),
        severity=Severity.HIGH,
        confidence=0.9,
        reason="TLS certificate verification is disabled.",
        recommendation="Keep certificate verification enabled; pin or provision the "
        "correct CA bundle instead of disabling verification.",
    ),
    RegexRule(
        rule="WILDCARD_CORS",
        pattern=re.compile(r"""Access-Control-Allow-Origin['"]?\s*[,:=]\s*['"]\*|allow_origins\s*=\s*\[\s*['"]\*"""),
        severity=Severity.MEDIUM,
        confidence=0.8,
        reason="CORS is opened to all origins.",
        recommendation="Restrict allowed origins to the domains that need access.",
    ),
    RegexRule(
        rule="JWT_VERIFICATION_WEAKENED",
        pattern=re.compile(r"""verify_signature['"]?\s*[:=]\s*False|algorithms\s*=\s*\[\s*['"]none"""),
        severity=Severity.CRITICAL,
        confidence=0.9,
        reason="JWT signature verification is weakened or disabled.",
        recommendation="Always verify JWT signatures with an allow-list of strong "
        "algorithms.",
    ),
)


class SecurityAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "security"

    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []
        for change in pr.files:
            if change.is_binary or change.change_type == ChangeType.DELETED:
                continue
            in_tests = paths.is_test_file(change.path)
            for diff_line in change.added_lines:
                stripped = diff_line.content.strip()
                for rule in LINE_RULES:
                    if rule.skip_comments and stripped.startswith(_COMMENT_PREFIXES):
                        continue
                    if rule.pattern.search(diff_line.content):
                        confidence = rule.confidence * (0.5 if in_tests else 1.0)
                        findings.append(
                            Finding(
                                category=Category.SECURITY,
                                severity=rule.severity,
                                confidence=round(confidence, 2),
                                file=change.path,
                                line=diff_line.line_number,
                                rule=rule.rule,
                                reason=rule.reason,
                                recommendation=rule.recommendation,
                                evidence=stripped[:200],
                            )
                        )

        findings.extend(self._path_findings(features))
        return findings

    def _path_findings(self, features: PRFeatures) -> list[Finding]:
        findings: list[Finding] = []
        for path in features.auth_files:
            findings.append(
                Finding(
                    category=Category.SECURITY,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    file=path,
                    rule="AUTH_CODE_MODIFIED",
                    reason="Authentication/authorization-related code was modified.",
                    recommendation="Request a security-focused review and verify "
                    "authentication and authorization test coverage.",
                )
            )
        for path in features.payment_files:
            findings.append(
                Finding(
                    category=Category.SECURITY,
                    severity=Severity.HIGH,
                    confidence=0.7,
                    file=path,
                    rule="PAYMENT_CODE_MODIFIED",
                    reason="Payment-related code was modified.",
                    recommendation="Require a second reviewer for payment flows and "
                    "verify idempotency and audit logging.",
                )
            )
        return findings

    @staticmethod
    def rules() -> list[tuple[str, str, str]]:
        """(rule id, severity, reason) catalog for documentation and the CLI."""
        catalog = [(r.rule, r.severity.value, r.reason) for r in LINE_RULES]
        catalog.append(("AUTH_CODE_MODIFIED", "MEDIUM", "Authentication/authorization code modified."))
        catalog.append(("PAYMENT_CODE_MODIFIED", "HIGH", "Payment code modified."))
        return catalog
