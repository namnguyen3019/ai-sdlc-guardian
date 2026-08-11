from conftest import make_file, make_pr

from guardian.analyzers.complexity import ComplexityAnalyzer
from guardian.models.findings import Severity
from guardian.services.feature_extractor import extract_features


def analyze(*files):
    pr = make_pr(*files)
    return ComplexityAnalyzer().analyze(pr, extract_features(pr))


def test_large_pr_medium_then_high():
    medium = analyze(make_file("src/a.py", added=[(i, "x = 1") for i in range(1, 601)]))
    assert next(f for f in medium if f.rule == "LARGE_PR").severity == Severity.MEDIUM

    high = analyze(make_file("src/a.py", added=[(i, "x = 1") for i in range(1, 1201)]))
    assert next(f for f in high if f.rule == "LARGE_PR").severity == Severity.HIGH


def test_many_files_changed():
    files = [make_file(f"src/f{i}.py", added=[(1, "x = 1")]) for i in range(25)]
    findings = analyze(*files)
    assert any(f.rule == "MANY_FILES_CHANGED" for f in findings)


def test_exception_handling_removed():
    findings = analyze(
        make_file(
            "src/svc.py",
            removed=[(30, "    except GatewayError:"), (31, "        retry()")],
        )
    )
    finding = next(f for f in findings if f.rule == "EXCEPTION_HANDLING_REMOVED")
    assert finding.severity == Severity.HIGH
    assert finding.line == 30


def test_broad_exception_handler_added():
    findings = analyze(make_file("src/svc.py", added=[(12, "    except:")]))
    assert any(f.rule == "BROAD_EXCEPTION_HANDLER" for f in findings)


def test_deep_nesting():
    findings = analyze(make_file("src/svc.py", added=[(9, " " * 24 + "flag = True")]))
    assert any(f.rule == "DEEP_NESTING" for f in findings)


def test_small_clean_change_is_quiet():
    findings = analyze(make_file("src/svc.py", added=[(1, "x = 1")]))
    assert findings == []
