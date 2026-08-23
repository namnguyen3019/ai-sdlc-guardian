import pytest

from guardian.benchmark.swebench import build_bug_record, collect_bug_records, rows_url
from guardian.benchmark.schema import (
    BenchmarkCategory,
    DiffDirection,
    LabelStatus,
    SourceKind,
)

FIX_PATCH = """diff --git a/pkg/calc.py b/pkg/calc.py
--- a/pkg/calc.py
+++ b/pkg/calc.py
@@ -5,3 +5,3 @@ def mean(values):
     total = sum(values)
-    return total / max(len(values), 1)
+    return total / len(values) if values else 0.0
"""


def row(instance_id="acme__pkg-123", repo="acme/pkg", patch=FIX_PATCH):
    return {"instance_id": instance_id, "repo": repo, "base_commit": "beefcafe", "patch": patch}


def test_rows_url_encodes_dataset():
    url = rows_url(200)
    assert "princeton-nlp%2FSWE-bench" in url
    assert "offset=200" in url


def test_build_bug_record_reverses_fix():
    record, reversed_text = build_bug_record(row(), license_spdx="BSD-3-Clause")
    assert record.id == "swebench-acme__pkg-123"
    assert record.category == BenchmarkCategory.BUG
    assert record.is_risky
    assert record.source == SourceKind.CURATED_DATASET
    assert record.direction == DiffDirection.REVERSED_FIX
    assert record.label_status == LabelStatus.CONFIRMED
    assert record.provenance.repository == "acme/pkg"
    assert record.provenance.commit_sha == "beefcafe"
    assert record.provenance.license_spdx == "BSD-3-Clause"
    # The reversed patch re-introduces the buggy line.
    assert "+    return total / max(len(values), 1)" in reversed_text


def test_build_bug_record_rejects_bad_rows():
    with pytest.raises(ValueError, match="instance_id"):
        build_bug_record({"repo": "a/b", "patch": FIX_PATCH})
    with pytest.raises(ValueError, match="empty patch"):
        build_bug_record(row(patch="  "))
    with pytest.raises(ValueError, match="too large"):
        build_bug_record(row(patch=FIX_PATCH + "+x\n" * 3000))


def test_collect_paginates_dedups_and_limits():
    pages = {
        0: [row("a__1"), row("a__2"), row("bad", patch="")],
        100: [row("a__3"), row("a__4")],
        200: [],
    }

    def fetch_json(url):
        offset = int(url.split("offset=")[1].split("&")[0])
        return {"rows": [{"row": r} for r in pages.get(offset, [])]}

    collected = collect_bug_records(
        fetch_json=fetch_json,
        limit=2,
        skip_ids={"swebench-a__1"},
        license_lookup=lambda repo: "MIT",
    )
    ids = [record.id for record, _ in collected]
    assert ids == ["swebench-a__2", "swebench-a__3"]
    assert collected[0][0].provenance.license_spdx == "MIT"
