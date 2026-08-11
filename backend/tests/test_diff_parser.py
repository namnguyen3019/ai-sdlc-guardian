from guardian.github.diff_parser import parse_diff
from guardian.models.pr import ChangeType


def test_parse_modified_files(fixtures_dir):
    files = parse_diff((fixtures_dir / "risky_payment.diff").read_text())
    assert [f.path for f in files] == [
        "src/payment/payment_service.py",
        "src/auth/login.py",
        "requirements.txt",
    ]
    payment = files[0]
    assert payment.change_type == ChangeType.MODIFIED
    assert payment.additions == 5
    assert payment.deletions == 6
    # Line numbers refer to the new file for added lines.
    sql_line = payment.added_lines[0]
    assert sql_line.line_number == 81
    assert "SELECT * FROM payments" in sql_line.content
    secret_line = next(l for l in payment.added_lines if "api_key" in l.content)
    assert secret_line.line_number == 85
    # Removed lines refer to the old file.
    assert payment.removed_lines[0].line_number == 81


def test_parse_new_file(fixtures_dir):
    files = parse_diff((fixtures_dir / "safe_docs.diff").read_text())
    new_test = files[2]
    assert new_test.path == "tests/test_format.py"
    assert new_test.change_type == ChangeType.ADDED
    assert new_test.additions == 5
    assert new_test.deletions == 0
    assert new_test.added_lines[0].line_number == 1


def test_parse_deleted_file():
    diff = """diff --git a/src/old.py b/src/old.py
deleted file mode 100644
index 8888888..0000000
--- a/src/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def old():
-    pass
"""
    files = parse_diff(diff)
    assert len(files) == 1
    assert files[0].path == "src/old.py"
    assert files[0].change_type == ChangeType.DELETED
    assert files[0].deletions == 2


def test_parse_renamed_file():
    diff = """diff --git a/src/a.py b/src/b.py
similarity index 100%
rename from src/a.py
rename to src/b.py
"""
    files = parse_diff(diff)
    assert files[0].change_type == ChangeType.RENAMED
    assert files[0].old_path == "src/a.py"
    assert files[0].path == "src/b.py"


def test_parse_binary_file():
    diff = """diff --git a/logo.png b/logo.png
index 1111111..2222222 100644
Binary files a/logo.png and b/logo.png differ
"""
    files = parse_diff(diff)
    assert files[0].is_binary
    assert files[0].additions == 0


def test_parse_empty_diff():
    assert parse_diff("") == []


def test_patch_preserved(fixtures_dir):
    files = parse_diff((fixtures_dir / "risky_payment.diff").read_text())
    assert files[0].patch.startswith("diff --git")
    assert "@@" in files[0].patch
