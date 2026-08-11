"""Path classification heuristics shared by feature extraction and analyzers.

All checks are case-insensitive substring / extension heuristics on the file
path only — file *content* signals live in the individual analyzers.
"""

from __future__ import annotations

import re

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".php", ".kt", ".swift",
    ".scala", ".m", ".mm",
}

CONFIG_EXTENSIONS = {".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties", ".env"}

_TEST_PATTERNS = re.compile(
    r"(^|/)(tests?|__tests__|spec)(/|$)|(^|/)test_[^/]+$|_test\.[^/.]+$|\.(test|spec)\.[^/.]+$",
    re.IGNORECASE,
)
_DB_PATTERNS = re.compile(
    r"(^|/)(migrations?|migrate|alembic|schemas?|db|database)(/|$)|\.sql$|schema\.[^/.]+$|(^|/)models\.py$",
    re.IGNORECASE,
)
_AUTH_PATTERNS = re.compile(
    r"auth|login|logout|session|oauth|sso|saml|jwt|permission|rbac|acl|password|credential|token",
    re.IGNORECASE,
)
_PAYMENT_PATTERNS = re.compile(
    r"payment|billing|checkout|invoice|stripe|paypal|refund|wallet|ledger",
    re.IGNORECASE,
)
_API_PATTERNS = re.compile(
    r"(^|/)(api|apis|routes?|routers?|controllers?|endpoints?|handlers?|views)(/|\.)|openapi|swagger|\.proto$|graphql",
    re.IGNORECASE,
)
_CI_PATTERNS = re.compile(
    r"(^|/)\.github/workflows/|(^|/)\.gitlab-ci\.yml$|(^|/)Jenkinsfile$|buildspec\.ya?ml$|(^|/)\.circleci/",
    re.IGNORECASE,
)
_INFRA_PATTERNS = re.compile(
    r"\.tf$|(^|/)(terraform|infra|infrastructure|cloudformation|cdk)(/|$)|(^|/)Dockerfile[^/]*$|docker-compose|(^|/)helm/|(^|/)k8s/|(^|/)charts?/",
    re.IGNORECASE,
)

DEPENDENCY_MANIFESTS = {
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "pipfile", "package.json", "pom.xml", "build.gradle", "build.gradle.kts",
    "go.mod", "cargo.toml", "gemfile", "composer.json", "mix.exs",
}
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "pipfile.lock",
    "uv.lock", "go.sum", "cargo.lock", "gemfile.lock", "composer.lock",
}


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1].lower()


def is_test_file(path: str) -> bool:
    return bool(_TEST_PATTERNS.search(path))


def is_source_file(path: str) -> bool:
    return any(path.lower().endswith(ext) for ext in SOURCE_EXTENSIONS)


def is_config_file(path: str) -> bool:
    base = _basename(path)
    if base in DEPENDENCY_MANIFESTS or base in LOCKFILES:
        return False
    return any(base.endswith(ext) for ext in CONFIG_EXTENSIONS) or base.startswith(".env")


def is_database_file(path: str) -> bool:
    return bool(_DB_PATTERNS.search(path))


def is_auth_file(path: str) -> bool:
    return not is_test_file(path) and bool(_AUTH_PATTERNS.search(path))


def is_payment_file(path: str) -> bool:
    return not is_test_file(path) and bool(_PAYMENT_PATTERNS.search(path))


def is_api_file(path: str) -> bool:
    return bool(_API_PATTERNS.search(path))


def is_dependency_manifest(path: str) -> bool:
    return _basename(path) in DEPENDENCY_MANIFESTS


def is_lockfile(path: str) -> bool:
    return _basename(path) in LOCKFILES


def is_ci_file(path: str) -> bool:
    return bool(_CI_PATTERNS.search(path))


def is_infra_file(path: str) -> bool:
    return bool(_INFRA_PATTERNS.search(path))


def is_critical_module(path: str, extra_patterns: list[str] | None = None) -> bool:
    if is_auth_file(path) or is_payment_file(path) or is_database_file(path):
        return True
    lowered = path.lower()
    return any(p.lower() in lowered for p in (extra_patterns or []))
