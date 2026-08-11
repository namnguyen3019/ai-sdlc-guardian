"""Turn a parsed PR into deterministic features used by analyzers and scoring."""

from __future__ import annotations

from guardian.analyzers import paths
from guardian.models.config import GuardianConfig
from guardian.models.features import PRFeatures
from guardian.models.pr import ChangeType, PRContext


def extract_features(pr: PRContext, config: GuardianConfig | None = None) -> PRFeatures:
    config = config or GuardianConfig()
    features = PRFeatures(
        files_changed=len(pr.files),
        lines_added=pr.total_additions,
        lines_deleted=pr.total_deletions,
    )
    for change in pr.files:
        path = change.path
        if change.change_type == ChangeType.DELETED:
            features.deleted_files.append(path)
        if paths.is_test_file(path):
            features.test_files.append(path)
        elif paths.is_source_file(path):
            features.source_files.append(path)
        if paths.is_config_file(path):
            features.config_files.append(path)
        if paths.is_database_file(path):
            features.database_files.append(path)
        if paths.is_auth_file(path):
            features.auth_files.append(path)
        if paths.is_payment_file(path):
            features.payment_files.append(path)
        if paths.is_api_file(path):
            features.api_files.append(path)
        if paths.is_dependency_manifest(path) or paths.is_lockfile(path):
            features.dependency_files.append(path)
        if paths.is_ci_file(path):
            features.ci_files.append(path)
        if paths.is_infra_file(path):
            features.infra_files.append(path)
        if paths.is_critical_module(path, config.critical_module_patterns):
            features.critical_files.append(path)
    return features
