from conftest import make_file, make_pr

from guardian.github.pr_loader import load_pr
from guardian.models.pr import ChangeType
from guardian.services.feature_extractor import extract_features


def test_features_from_risky_fixture(fixtures_dir):
    pr = load_pr(fixtures_dir / "risky_payment.diff")
    features = extract_features(pr)

    assert features.files_changed == 3
    assert features.lines_added == pr.total_additions
    assert features.source_files_changed == 2
    assert features.test_files_changed == 0
    assert features.auth_files == ["src/auth/login.py"]
    assert features.payment_files == ["src/payment/payment_service.py"]
    assert "requirements.txt" in features.dependency_files
    assert set(features.critical_files) == {
        "src/payment/payment_service.py",
        "src/auth/login.py",
    }


def test_deleted_and_test_classification():
    pr = make_pr(
        make_file("src/old.py", removed=[(1, "x = 1")], change_type=ChangeType.DELETED),
        make_file("tests/test_new.py", added=[(1, "def test_x(): pass")]),
    )
    features = extract_features(pr)
    assert features.deleted_files == ["src/old.py"]
    assert features.test_files == ["tests/test_new.py"]
    assert features.source_files == ["src/old.py"]  # tests are not source
