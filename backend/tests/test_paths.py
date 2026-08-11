from guardian.analyzers import paths


def test_test_files():
    assert paths.is_test_file("tests/test_login.py")
    assert paths.is_test_file("src/__tests__/app.test.tsx")
    assert paths.is_test_file("pkg/handler_test.go")
    assert paths.is_test_file("spec/models/user_spec.rb")
    assert not paths.is_test_file("src/attestation.py")


def test_source_files():
    assert paths.is_source_file("src/app.py")
    assert paths.is_source_file("web/index.tsx")
    assert not paths.is_source_file("README.md")


def test_config_files():
    assert paths.is_config_file("config/settings.yaml")
    assert paths.is_config_file(".env.production")
    assert not paths.is_config_file("package.json")  # dependency manifest, not config
    assert not paths.is_config_file("poetry.lock")


def test_database_files():
    assert paths.is_database_file("migrations/0042_add_index.py")
    assert paths.is_database_file("db/schema.sql")
    assert not paths.is_database_file("src/views/home.py")


def test_auth_and_payment_files():
    assert paths.is_auth_file("src/auth/login.py")
    assert paths.is_auth_file("services/session_manager.ts")
    assert not paths.is_auth_file("tests/test_auth.py")  # tests are not flagged
    assert paths.is_payment_file("src/billing/invoice.py")
    assert not paths.is_payment_file("src/utils/format.py")


def test_api_files():
    assert paths.is_api_file("src/api/users.py")
    assert paths.is_api_file("app/routes/orders.ts")
    assert paths.is_api_file("proto/orders.proto")
    assert not paths.is_api_file("src/utils/format.py")


def test_dependency_files():
    assert paths.is_dependency_manifest("requirements.txt")
    assert paths.is_dependency_manifest("frontend/package.json")
    assert paths.is_lockfile("poetry.lock")
    assert not paths.is_dependency_manifest("src/app.py")


def test_ci_and_infra_files():
    assert paths.is_ci_file(".github/workflows/ci.yml")
    assert paths.is_infra_file("infrastructure/lib/stack.ts")
    assert paths.is_infra_file("Dockerfile")
    assert not paths.is_ci_file("src/app.py")


def test_critical_modules():
    assert paths.is_critical_module("src/auth/login.py")
    assert paths.is_critical_module("src/payment/charge.py")
    assert paths.is_critical_module("migrations/0001_init.py")
    assert not paths.is_critical_module("src/utils/format.py")
    assert paths.is_critical_module("core/engine.py", extra_patterns=["core/engine"])
