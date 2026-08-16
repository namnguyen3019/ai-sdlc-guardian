from guardian.benchmark.dataset import (
    composition,
    existing_ids,
    load_diff,
    load_records,
    save_record,
)
from guardian.benchmark.schema import (
    BenchmarkCategory,
    BenchmarkRecord,
    LabelStatus,
    SourceKind,
    Split,
)

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"


def make_record(record_id: str, **overrides) -> BenchmarkRecord:
    defaults = dict(
        id=record_id,
        category=BenchmarkCategory.NORMAL,
        is_risky=False,
        source=SourceKind.MINED,
    )
    defaults.update(overrides)
    return BenchmarkRecord(**defaults)


def test_save_and_load_roundtrip(tmp_path):
    record = make_record("mined-acme-shop-1", notes="hello")
    save_record(tmp_path, record, DIFF)
    save_record(tmp_path, make_record("mined-acme-shop-2"), DIFF)

    loaded = load_records(tmp_path)
    assert [r.id for r in loaded] == ["mined-acme-shop-1", "mined-acme-shop-2"]
    assert loaded[0].notes == "hello"
    assert load_diff(tmp_path, loaded[0]) == DIFF
    assert existing_ids(tmp_path) == {"mined-acme-shop-1", "mined-acme-shop-2"}


def test_split_is_deterministic_and_reasonably_balanced():
    records = [make_record(f"record-{i}") for i in range(500)]
    first = [r.split for r in records]
    second = [make_record(f"record-{i}").split for i in range(500)]
    assert first == second  # same ids → same splits, always

    holdout = sum(1 for s in first if s == Split.HOLDOUT)
    assert 100 <= holdout <= 200  # ~30% of 500, generous tolerance


def test_composition_counts():
    records = [
        make_record("a", category=BenchmarkCategory.SECURITY, is_risky=True, label_status=LabelStatus.CONFIRMED),
        make_record("b"),
        make_record("c", source=SourceKind.SYNTHETIC, label_status=LabelStatus.CONFIRMED),
    ]
    stats = composition(records)
    assert stats["total"] == 3
    assert stats["by_category"]["security"] == 1
    assert stats["by_source"]["synthetic"] == 1
    assert stats["risky"] == 1 and stats["not_risky"] == 2
    assert set(stats["by_split"]) <= {"calibration", "holdout"}
