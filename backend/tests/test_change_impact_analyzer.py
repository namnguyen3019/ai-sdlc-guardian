from conftest import make_file, make_pr

from guardian.analyzers.change_impact import ChangeImpactAnalyzer
from guardian.models.pr import ChangeType
from guardian.services.feature_extractor import extract_features


def analyze(*files):
    pr = make_pr(*files)
    return ChangeImpactAnalyzer().analyze(pr, extract_features(pr))


def rules_found(findings):
    return {f.rule for f in findings}


def test_critical_module_and_database():
    findings = analyze(
        make_file("src/auth/login.py", added=[(1, "x = 1")]),
        make_file("migrations/0042_drop_column.sql", added=[(1, "ALTER TABLE users DROP COLUMN email;")]),
    )
    assert "CRITICAL_MODULE_MODIFIED" in rules_found(findings)
    assert "DATABASE_SCHEMA_CHANGED" in rules_found(findings)


def test_config_ci_and_infra():
    findings = analyze(
        make_file("config/settings.yaml", added=[(1, "debug: false")]),
        make_file(".github/workflows/deploy.yml", added=[(1, "on: push")]),
        make_file("infrastructure/lib/stack.ts", added=[(1, "new Bucket(this)")]),
    )
    assert {"CONFIGURATION_CHANGED", "CI_PIPELINE_CHANGED", "INFRASTRUCTURE_CHANGED"} <= rules_found(findings)


def test_source_file_deleted():
    findings = analyze(
        make_file("src/legacy.py", removed=[(1, "x = 1")], change_type=ChangeType.DELETED)
    )
    assert "SOURCE_FILE_DELETED" in rules_found(findings)


def test_api_contract_changed():
    findings = analyze(
        make_file(
            "src/api/users.py",
            removed=[(12, '@app.get("/users/{id}")'), (13, "def get_user(id):")],
            added=[(12, '@app.get("/v2/accounts/{id}")'), (13, "def get_account(id):")],
        ),
        make_file(
            "src/api/orders.py",
            removed=[(30, '@app.delete("/orders/{id}")'), (31, "def delete_order(id):")],
        ),
    )
    api_findings = [f for f in findings if f.rule == "API_CONTRACT_CHANGED"]
    assert len(api_findings) == 1
    assert api_findings[0].file == "src/api/orders.py"


def test_quiet_change():
    findings = analyze(make_file("src/utils/format.py", added=[(1, "x = 1")]))
    assert findings == []
