import pytest

from guardian.benchmark.reverse_diff import ReverseDiffError, reverse_diff
from guardian.github.diff_parser import parse_diff
from guardian.models.pr import ChangeType

FIX_DIFF = """diff --git a/src/db.py b/src/db.py
index 1111111..2222222 100644
--- a/src/db.py
+++ b/src/db.py
@@ -10,4 +10,4 @@ def get_user(uid):
     conn = pool.acquire()
-    cur.execute(f"SELECT * FROM users WHERE id = {uid}")
+    cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
     return cur.fetchone()
"""


def test_reverse_swaps_additions_and_removals():
    reversed_text = reverse_diff(FIX_DIFF)
    files = parse_diff(reversed_text)
    assert len(files) == 1
    # The reversed change *introduces* the injection-prone line.
    added = [l.content for l in files[0].added_lines]
    removed = [l.content for l in files[0].removed_lines]
    assert any("SELECT * FROM users WHERE id = {uid}" in line for line in added)
    assert any("WHERE id = ?" in line for line in removed)


def test_reverse_swaps_hunk_ranges_and_headers():
    reversed_text = reverse_diff(
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -5,3 +7,4 @@ def f():\n"
        " ctx\n"
        "+added\n"
        " ctx2\n"
    )
    assert "@@ -7,4 +5,3 @@ def f():" in reversed_text
    assert "\n-added\n" in reversed_text


def test_reverse_is_an_involution():
    assert reverse_diff(reverse_diff(FIX_DIFF)) == FIX_DIFF


def test_new_file_becomes_deleted_file():
    new_file = (
        "diff --git a/added.py b/added.py\n"
        "new file mode 100644\n"
        "index 0000000..abcdef0\n"
        "--- /dev/null\n"
        "+++ b/added.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+import os\n"
        "+print(os.name)\n"
    )
    files = parse_diff(reverse_diff(new_file))
    assert files[0].change_type == ChangeType.DELETED
    assert files[0].deletions == 2


def test_binary_diff_rejected():
    with pytest.raises(ReverseDiffError):
        reverse_diff("diff --git a/logo.png b/logo.png\nBinary files a/logo.png and b/logo.png differ\n")


def test_rename_swapped():
    renamed = (
        "diff --git a/old.py b/new.py\n"
        "similarity index 100%\n"
        "rename from old.py\n"
        "rename to new.py\n"
    )
    files = parse_diff(reverse_diff(renamed))
    assert files[0].old_path == "new.py"
    assert files[0].path == "old.py"
