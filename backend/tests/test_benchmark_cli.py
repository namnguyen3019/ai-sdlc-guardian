import json

import pytest

from guardian.benchmark.cli import main
from guardian.benchmark.dataset import save_record
from guardian.benchmark.schema import (
    BenchmarkCategory,
    BenchmarkRecord,
    LabelStatus,
    Provenance,
    SourceKind,
)

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"


@pytest.fixture
def dataset(tmp_path):
    record = BenchmarkRecord(
        id="osv-ghsa-test",
        category=BenchmarkCategory.SECURITY,
        is_risky=True,
        source=SourceKind.CURATED_OSV,
        label_status=LabelStatus.CONFIRMED,
        provenance=Provenance(repository="acme/app", commit_sha="abc", advisory_id="GHSA-test"),
    )
    save_record(tmp_path, record, DIFF)
    return tmp_path


def test_validate_ok(dataset, capsys):
    assert main(["validate", "--dataset", str(dataset)]) == 0
    assert "1 records valid" in capsys.readouterr().out


def test_validate_failure_exits_nonzero(dataset, capsys):
    (dataset / "diffs" / "osv-ghsa-test.diff").unlink()
    assert main(["validate", "--dataset", str(dataset)]) == 1
    assert "INVALID" in capsys.readouterr().err


def test_stats_prints_composition(dataset, capsys):
    assert main(["stats", "--dataset", str(dataset)]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["total"] == 1
    assert stats["by_category"] == {"security": 1}


def test_fetch_osv_requires_token(dataset, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main(["fetch-osv", "--dataset", str(dataset)])
