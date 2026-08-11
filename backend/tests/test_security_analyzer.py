from conftest import make_file, make_pr

from guardian.analyzers.security import SecurityAnalyzer
from guardian.models.findings import Severity
from guardian.services.feature_extractor import extract_features


def analyze(*files):
    pr = make_pr(*files)
    return SecurityAnalyzer().analyze(pr, extract_features(pr))


def rules_found(findings):
    return {f.rule for f in findings}


def test_sql_injection_fstring():
    findings = analyze(
        make_file("src/db.py", added=[(10, '    cur.execute(f"SELECT * FROM users WHERE id = {uid}")')])
    )
    sql = [f for f in findings if f.rule == "SQL_INJECTION_RISK"]
    assert len(sql) == 1
    assert sql[0].severity == Severity.CRITICAL
    assert sql[0].file == "src/db.py"
    assert sql[0].line == 10
    assert sql[0].evidence


def test_sql_injection_concatenation():
    findings = analyze(
        make_file("src/db.py", added=[(3, '    q = "SELECT name FROM users WHERE id = " + user_id')])
    )
    assert "SQL_INJECTION_RISK" in rules_found(findings)


def test_hardcoded_secret():
    findings = analyze(
        make_file("src/settings.py", added=[(5, 'API_KEY = "sk_live_abcdef123456"')])
    )
    secret = next(f for f in findings if f.rule == "HARDCODED_SECRET")
    assert secret.severity == Severity.CRITICAL


def test_dynamic_code_and_shell():
    findings = analyze(
        make_file(
            "src/runner.py",
            added=[
                (1, "result = eval(user_input)"),
                (2, "subprocess.run(cmd, shell=True)"),
            ],
        )
    )
    assert {"CODE_INJECTION_RISK", "SHELL_INJECTION_RISK"} <= rules_found(findings)


def test_unsafe_deserialization_and_tls():
    findings = analyze(
        make_file(
            "src/io.py",
            added=[
                (1, "data = pickle.loads(blob)"),
                (2, "requests.get(url, verify=False)"),
            ],
        )
    )
    assert {"UNSAFE_DESERIALIZATION", "TLS_VERIFICATION_DISABLED"} <= rules_found(findings)


def test_comment_lines_skipped_for_code_rules():
    findings = analyze(
        make_file("src/app.py", added=[(1, "# eval(user_input) would be dangerous")])
    )
    assert "CODE_INJECTION_RISK" not in rules_found(findings)


def test_confidence_halved_in_test_files():
    findings = analyze(
        make_file("tests/test_db.py", added=[(1, 'cur.execute(f"SELECT * FROM t WHERE id = {i}")')])
    )
    sql = next(f for f in findings if f.rule == "SQL_INJECTION_RISK")
    assert sql.confidence < 0.5


def test_auth_and_payment_path_findings():
    findings = analyze(
        make_file("src/auth/login.py", added=[(1, "x = 1")]),
        make_file("src/payment/charge.py", added=[(1, "y = 2")]),
    )
    assert {"AUTH_CODE_MODIFIED", "PAYMENT_CODE_MODIFIED"} <= rules_found(findings)


def test_clean_code_produces_no_line_findings():
    findings = analyze(
        make_file("src/utils/format.py", added=[(1, "def add(a, b):"), (2, "    return a + b")])
    )
    assert findings == []
