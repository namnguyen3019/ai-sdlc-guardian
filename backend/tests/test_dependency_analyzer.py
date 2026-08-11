from conftest import make_file, make_pr

from guardian.analyzers.dependency import DependencyAnalyzer
from guardian.services.feature_extractor import extract_features


def analyze(*files):
    pr = make_pr(*files)
    return DependencyAnalyzer().analyze(pr, extract_features(pr))


def rules_found(findings):
    return {f.rule for f in findings}


def test_manifest_change_with_new_and_unpinned_deps():
    findings = analyze(
        make_file(
            "requirements.txt",
            added=[(3, "left-pad-py>=1.0"), (4, "totally-new-lib==0.0.1")],
        )
    )
    rules = rules_found(findings)
    assert "DEPENDENCY_MANIFEST_CHANGED" in rules
    assert "UNPINNED_DEPENDENCY_VERSION" in rules
    new_deps = [f for f in findings if f.rule == "NEW_DEPENDENCY_ADDED"]
    assert {f.evidence for f in new_deps} == {"left-pad-py>=1.0", "totally-new-lib==0.0.1"}


def test_version_bump_is_not_new_dependency():
    findings = analyze(
        make_file(
            "requirements.txt",
            removed=[(1, "flask==2.3.0")],
            added=[(1, "flask==3.0.0")],
        )
    )
    assert "NEW_DEPENDENCY_ADDED" not in rules_found(findings)
    assert "DEPENDENCY_MANIFEST_CHANGED" in rules_found(findings)


def test_lockfile_only_change():
    findings = analyze(make_file("poetry.lock", added=[(1, 'name = "urllib3"')]))
    assert rules_found(findings) == {"LOCKFILE_ONLY_CHANGE"}


def test_lockfile_with_manifest_is_not_flagged_as_lockfile_only():
    findings = analyze(
        make_file("pyproject.toml", added=[(10, '"httpx>=0.27",')]),
        make_file("poetry.lock", added=[(1, 'name = "httpx"')]),
    )
    assert "LOCKFILE_ONLY_CHANGE" not in rules_found(findings)


def test_no_dependency_changes():
    findings = analyze(make_file("src/app.py", added=[(1, "x = 1")]))
    assert findings == []
