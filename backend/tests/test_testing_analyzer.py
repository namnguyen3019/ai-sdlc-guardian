from conftest import make_file, make_pr

from guardian.analyzers.testing import TestingAnalyzer
from guardian.models.findings import Severity
from guardian.models.pr import ChangeType
from guardian.services.feature_extractor import extract_features


def analyze(*files):
    pr = make_pr(*files)
    return TestingAnalyzer().analyze(pr, extract_features(pr))


def test_source_without_tests():
    big_file = make_file("src/service.py", added=[(i, f"line_{i} = {i}") for i in range(1, 41)])
    findings = analyze(big_file)
    finding = next(f for f in findings if f.rule == "SOURCE_CHANGED_WITHOUT_TESTS")
    assert finding.severity == Severity.MEDIUM
    assert "40 lines" in finding.reason


def test_large_source_without_tests_is_high():
    big_file = make_file("src/service.py", added=[(i, f"line_{i} = {i}") for i in range(1, 101)])
    findings = analyze(big_file)
    finding = next(f for f in findings if f.rule == "SOURCE_CHANGED_WITHOUT_TESTS")
    assert finding.severity == Severity.HIGH


def test_source_with_tests_is_quiet():
    findings = analyze(
        make_file("src/service.py", added=[(i, f"line_{i} = {i}") for i in range(1, 41)]),
        make_file("tests/test_service.py", added=[(1, "def test_service(): pass")]),
    )
    assert all(f.rule != "SOURCE_CHANGED_WITHOUT_TESTS" for f in findings)


def test_auth_change_without_tests():
    findings = analyze(make_file("src/auth/session.py", added=[(1, "TTL = 3600")]))
    assert any(f.rule == "AUTH_CHANGE_WITHOUT_TESTS" for f in findings)


def test_test_file_deleted():
    findings = analyze(
        make_file(
            "tests/test_old.py",
            removed=[(1, "def test_old(): pass")],
            change_type=ChangeType.DELETED,
        )
    )
    assert any(f.rule == "TEST_FILE_DELETED" for f in findings)


def test_test_cases_removed():
    findings = analyze(
        make_file(
            "tests/test_api.py",
            removed=[(10, "def test_delete_user():"), (20, "def test_rate_limit():")],
            added=[(10, "def test_delete_user():")],
        )
    )
    finding = next(f for f in findings if f.rule == "TEST_CASES_REMOVED")
    assert "1 test case(s)" in finding.reason
