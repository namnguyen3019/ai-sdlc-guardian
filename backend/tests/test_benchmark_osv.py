import pytest

from guardian.benchmark.osv import (
    FixCommit,
    build_security_record,
    collect_security_records,
    find_fix_commit,
)
from guardian.benchmark.schema import DiffDirection, LabelStatus, Split

FIX_DIFF = """diff --git a/app/auth.py b/app/auth.py
index aaa1111..bbb2222 100644
--- a/app/auth.py
+++ b/app/auth.py
@@ -20,3 +20,3 @@ def check(token):
 def verify(token):
-    return jwt.decode(token, key, options={"verify_signature": False})
+    return jwt.decode(token, key, algorithms=["HS256"])
"""


def osv_record(advisory_id="GHSA-abcd-1234-wxyz", fix_url="https://github.com/acme/app/commit/deadbeefcafe"):
    return {
        "id": advisory_id,
        "references": [
            {"type": "ADVISORY", "url": "https://example.com/advisory"},
            {"type": "FIX", "url": fix_url},
        ],
        "database_specific": {"cwe_ids": ["CWE-347"]},
    }


class StubGitHub:
    def __init__(self, diff=FIX_DIFF, license_spdx="MIT"):
        self.diff = diff
        self.license_spdx = license_spdx

    def get_commit_diff(self, repository, sha):
        return self.diff

    def get_repo_license(self, repository):
        return self.license_spdx


def test_find_fix_commit():
    fix = find_fix_commit(osv_record())
    assert fix == FixCommit(
        advisory_id="GHSA-abcd-1234-wxyz",
        repository="acme/app",
        commit_sha="deadbeefcafe",
        cwe_ids=("CWE-347",),
        url="https://github.com/acme/app/commit/deadbeefcafe",
    )


def test_find_fix_commit_absent_or_not_github():
    record = osv_record()
    record["references"] = [{"type": "WEB", "url": "https://example.com"}]
    assert find_fix_commit(record) is None
    assert find_fix_commit(osv_record(fix_url="https://gitlab.com/x/y/commit/abc123")) is None


def test_find_fix_commit_accepts_web_typed_commit_links():
    # GHSA-sourced OSV records typically use WEB references for fix commits.
    record = {
        "id": "GHSA-web-only",
        "references": [
            {"type": "WEB", "url": "https://github.com/acme/app/security/advisories/GHSA-web-only"},
            {"type": "WEB", "url": "https://github.com/acme/app/commit/0abbc838bae3394fe7491dad7009670d4e3b6cf8"},
            {"type": "PACKAGE", "url": "https://github.com/acme/app"},
        ],
    }
    fix = find_fix_commit(record)
    assert fix is not None
    assert fix.repository == "acme/app"
    assert fix.commit_sha == "0abbc838bae3394fe7491dad7009670d4e3b6cf8"


def test_find_fix_commit_prefers_fix_typed_reference():
    record = osv_record()
    record["references"].insert(
        0, {"type": "WEB", "url": "https://github.com/acme/app/commit/1111111111111111111111111111111111111111"}
    )
    fix = find_fix_commit(record)
    assert fix.commit_sha == "deadbeefcafe"  # the FIX-typed reference wins


def test_build_security_record_reverses_and_labels():
    fix = find_fix_commit(osv_record())
    record, reversed_text = build_security_record(fix, FIX_DIFF, license_spdx="MIT")

    assert record.id == "osv-ghsa-abcd-1234-wxyz"
    assert record.is_risky
    assert record.direction == DiffDirection.REVERSED_FIX
    assert record.label_status == LabelStatus.CONFIRMED
    assert record.provenance.cwe_ids == ["CWE-347"]
    assert record.provenance.license_spdx == "MIT"
    assert record.split in (Split.CALIBRATION, Split.HOLDOUT)
    # The reversed diff *adds* the vulnerable line.
    assert '+    return jwt.decode(token, key, options={"verify_signature": False})' in reversed_text


def test_build_security_record_rejects_empty_and_oversized():
    fix = find_fix_commit(osv_record())
    with pytest.raises(ValueError):
        build_security_record(fix, "")
    huge = FIX_DIFF + ("+pad\n" * 3000)
    with pytest.raises(ValueError):
        build_security_record(fix, huge)


def test_collect_skips_bad_advisories_and_respects_limit_and_dedup():
    responses = {
        "GHSA-good-0001": osv_record("GHSA-good-0001"),
        "GHSA-nofix-0002": {"id": "GHSA-nofix-0002", "references": []},
        "GHSA-boom-0003": None,  # fetch raises
        "GHSA-good-0004": osv_record("GHSA-good-0004"),
        "GHSA-good-0005": osv_record("GHSA-good-0005"),
    }

    def fetch_json(url):
        advisory_id = url.rsplit("/", 1)[-1]
        if responses[advisory_id] is None:
            raise RuntimeError("osv down")
        return responses[advisory_id]

    collected = collect_security_records(
        list(responses),
        StubGitHub(),
        fetch_json=fetch_json,
        limit=2,
        skip_ids={"osv-ghsa-good-0001"},  # already in the dataset
    )
    ids = [record.id for record, _ in collected]
    assert ids == ["osv-ghsa-good-0004", "osv-ghsa-good-0005"]
