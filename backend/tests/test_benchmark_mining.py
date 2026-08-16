from datetime import date

import pytest

from guardian.benchmark.cli import main
from guardian.benchmark.dataset import load_records, save_record, update_record
from guardian.benchmark.mining import (
    build_mined_record,
    collect_mined_records,
    record_id_for,
    suggest_category,
)
from guardian.benchmark.schema import BenchmarkCategory, LabelStatus, SourceKind

TODAY = date(2026, 8, 16)

DOCS_DIFF = (
    "diff --git a/README.md b/README.md\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -1,1 +1,2 @@\n"
    " # App\n"
    "+More docs.\n"
)
AUTH_DIFF = (
    "diff --git a/src/auth/session.py b/src/auth/session.py\n"
    "--- a/src/auth/session.py\n"
    "+++ b/src/auth/session.py\n"
    "@@ -1,1 +1,2 @@\n"
    " TTL = 100\n"
    "+GRACE = 30\n"
)


def pr_meta(number=7, merged_at="2025-01-10T12:00:00Z", **overrides):
    meta = {
        "number": number,
        "merged_at": merged_at,
        "merge_commit_sha": "cafe1234",
        "html_url": f"https://github.com/acme/app/pull/{number}",
    }
    meta.update(overrides)
    return meta


def test_suggest_category_by_paths():
    assert suggest_category(DOCS_DIFF) == BenchmarkCategory.NORMAL
    assert suggest_category(AUTH_DIFF) == BenchmarkCategory.AUTH_CHANGE


def test_build_mined_record_is_candidate_with_survival_note():
    record, diff = build_mined_record("acme/app", pr_meta(), DOCS_DIFF, "MIT", today=TODAY)
    assert record.id == record_id_for("acme/app", 7) == "mined-acme-app-pr7"
    assert record.source == SourceKind.MINED
    assert record.label_status == LabelStatus.CANDIDATE
    assert record.is_risky is False
    assert record.provenance.pr_number == 7
    assert record.provenance.license_spdx == "MIT"
    assert "survival age only" in record.notes
    assert diff == DOCS_DIFF


def test_build_mined_record_rejects_unmerged_young_empty_and_huge():
    with pytest.raises(ValueError, match="not merged"):
        build_mined_record("acme/app", pr_meta(merged_at=None), DOCS_DIFF, today=TODAY)
    with pytest.raises(ValueError, match="days ago"):
        build_mined_record("acme/app", pr_meta(merged_at="2026-07-01T00:00:00Z"), DOCS_DIFF, today=TODAY)
    with pytest.raises(ValueError, match="empty diff"):
        build_mined_record("acme/app", pr_meta(), "", today=TODAY)
    huge = DOCS_DIFF + "+pad\n" * 2000
    with pytest.raises(ValueError, match="too large"):
        build_mined_record("acme/app", pr_meta(), huge, today=TODAY)


class StubGitHub:
    def __init__(self, pulls, diffs):
        self.pulls = pulls  # {page: [meta, ...]}
        self.diffs = diffs  # {number: diff_text}

    def get_repo_license(self, repository):
        return "Apache-2.0"

    def list_pulls(self, repository, state="closed", per_page=100, page=1, direction="asc"):
        return self.pulls.get(page, [])

    def get_pr_diff(self, repository, pr_number):
        return self.diffs[pr_number]


def test_collect_respects_limit_dedup_and_skips_bad():
    github = StubGitHub(
        pulls={1: [pr_meta(1), pr_meta(2, merged_at=None), pr_meta(3), pr_meta(4)]},
        diffs={1: DOCS_DIFF, 3: AUTH_DIFF, 4: DOCS_DIFF},
    )
    collected = collect_mined_records(
        github, "acme/app", limit=2, skip_ids={"mined-acme-app-pr1"}
    )
    ids = [record.id for record, _ in collected]
    assert ids == ["mined-acme-app-pr3", "mined-acme-app-pr4"]
    assert collected[0][0].category == BenchmarkCategory.AUTH_CHANGE
    assert collected[0][0].provenance.license_spdx == "Apache-2.0"


def test_confirm_promotes_candidate(tmp_path, capsys):
    record, diff = build_mined_record("acme/app", pr_meta(), DOCS_DIFF, "MIT", today=TODAY)
    save_record(tmp_path, record, diff)

    code = main(
        [
            "confirm", "--dataset", str(tmp_path), "--id", record.id,
            "--not-risky", "--reviewed-by", "nam", "--reason", "docs only",
        ]
    )
    assert code == 0
    confirmed = load_records(tmp_path)[0]
    assert confirmed.label_status == LabelStatus.CONFIRMED
    assert confirmed.is_risky is False
    assert "confirmed not risky by nam" in confirmed.notes
    assert "docs only" in confirmed.notes


def test_confirm_unknown_id_fails(tmp_path):
    record, diff = build_mined_record("acme/app", pr_meta(), DOCS_DIFF, today=TODAY)
    save_record(tmp_path, record, diff)
    assert main(["confirm", "--dataset", str(tmp_path), "--id", "nope",
                 "--risky", "--reviewed-by", "nam"]) == 1


def test_update_record_unknown_id_raises(tmp_path):
    record, diff = build_mined_record("acme/app", pr_meta(), DOCS_DIFF, today=TODAY)
    save_record(tmp_path, record, diff)
    other = record.model_copy(update={"id": "different"})
    with pytest.raises(KeyError):
        update_record(tmp_path, other)
