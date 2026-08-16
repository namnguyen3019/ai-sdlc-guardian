from guardian.benchmark.dataset import dataset_paths, save_record
from guardian.benchmark.schema import (
    BenchmarkCategory,
    BenchmarkRecord,
    LabelStatus,
    Provenance,
    SourceKind,
)
from guardian.benchmark.validate import evaluation_ready, validate_dataset

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"


def confirmed_record(record_id="osv-ghsa-ok") -> BenchmarkRecord:
    return BenchmarkRecord(
        id=record_id,
        category=BenchmarkCategory.SECURITY,
        is_risky=True,
        source=SourceKind.CURATED_OSV,
        label_status=LabelStatus.CONFIRMED,
        provenance=Provenance(repository="acme/app", commit_sha="abc123", advisory_id="GHSA-ok"),
    )


def candidate_record(record_id="mined-1") -> BenchmarkRecord:
    return BenchmarkRecord(
        id=record_id,
        category=BenchmarkCategory.NORMAL,
        is_risky=False,
        source=SourceKind.MINED,
    )


def test_valid_dataset_passes(tmp_path):
    save_record(tmp_path, confirmed_record(), DIFF)
    save_record(tmp_path, candidate_record(), DIFF)
    assert validate_dataset(tmp_path) == []


def test_missing_dataset_and_missing_diff(tmp_path):
    assert validate_dataset(tmp_path / "nope") != []

    save_record(tmp_path, confirmed_record(), DIFF)
    _, diffs_dir = dataset_paths(tmp_path)
    (diffs_dir / "osv-ghsa-ok.diff").unlink()
    problems = validate_dataset(tmp_path)
    assert any("missing diff file" in p for p in problems)


def test_duplicate_ids_and_orphan_diffs_flagged(tmp_path):
    save_record(tmp_path, confirmed_record("dup"), DIFF)
    save_record(tmp_path, confirmed_record("dup"), DIFF)
    _, diffs_dir = dataset_paths(tmp_path)
    (diffs_dir / "orphan.diff").write_text(DIFF)

    problems = validate_dataset(tmp_path)
    assert any("duplicate id" in p for p in problems)
    assert any("orphan diff" in p for p in problems)


def test_unparseable_diff_flagged(tmp_path):
    save_record(tmp_path, confirmed_record(), "this is not a diff at all")
    problems = validate_dataset(tmp_path)
    assert any("zero file changes" in p for p in problems)


def test_confirmed_record_requires_provenance(tmp_path):
    bare = confirmed_record()
    bare.provenance = Provenance()
    save_record(tmp_path, bare, DIFF)
    problems = validate_dataset(tmp_path)
    assert any("lacks source repository" in p for p in problems)
    assert any("lacks advisory id" in p for p in problems)


def test_synthetic_must_be_confirmed(tmp_path):
    synthetic = candidate_record("synthetic-1")
    synthetic.source = SourceKind.SYNTHETIC
    save_record(tmp_path, synthetic, DIFF)
    assert any("must be confirmed" in p for p in validate_dataset(tmp_path))


def test_evaluation_ready_excludes_candidates():
    ready = evaluation_ready([confirmed_record(), candidate_record()])
    assert [r.id for r in ready] == ["osv-ghsa-ok"]
