import json

from guardian.cli import main


def test_analyze_json_output(fixtures_dir, tmp_path):
    out = tmp_path / "report.json"
    code = main(
        [
            "analyze",
            "--diff", str(fixtures_dir / "risky_payment.diff"),
            "--meta", str(fixtures_dir / "meta.json"),
            "--format", "json",
            "--output", str(out),
        ]
    )
    assert code == 0
    report = json.loads(out.read_text())
    assert report["repository"] == "acme/shop"
    assert report["pr_number"] == 42
    assert 0 <= report["overall_risk"] <= 100
    assert report["findings"]


def test_analyze_markdown_to_stdout(fixtures_dir, capsys):
    code = main(["analyze", "--diff", str(fixtures_dir / "safe_docs.diff")])
    assert code == 0
    captured = capsys.readouterr()
    assert "AI-SDLC Guardian" in captured.out
    assert "LOW" in captured.out


def test_fail_on_gate(fixtures_dir):
    code = main(
        ["analyze", "--diff", str(fixtures_dir / "risky_payment.diff"), "--fail-on", "MEDIUM"]
    )
    assert code == 1


def test_fail_on_gate_passes_safe_pr(fixtures_dir):
    code = main(
        ["analyze", "--diff", str(fixtures_dir / "safe_docs.diff"), "--fail-on", "MEDIUM"]
    )
    assert code == 0


def test_cli_overrides(fixtures_dir, tmp_path):
    out = tmp_path / "report.json"
    code = main(
        [
            "analyze",
            "--diff", str(fixtures_dir / "safe_docs.diff"),
            "--repo", "acme/other",
            "--pr", "7",
            "--format", "json",
            "--output", str(out),
        ]
    )
    assert code == 0
    report = json.loads(out.read_text())
    assert report["repository"] == "acme/other"
    assert report["pr_number"] == 7


def test_custom_config_weights(fixtures_dir, tmp_path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"weights": {"security": 1.0, "testing": 0, "change_impact": 0, "complexity": 0, "ai_risk": 0}})
    )
    out = tmp_path / "report.json"
    code = main(
        [
            "analyze",
            "--diff", str(fixtures_dir / "risky_payment.diff"),
            "--config", str(config),
            "--format", "json",
            "--output", str(out),
        ]
    )
    assert code == 0
    report = json.loads(out.read_text())
    # All weight on security; the risky fixture saturates the security dimension.
    assert report["overall_risk"] == report["scores"]["security"]


def test_rules_command(capsys):
    assert main(["rules"]) == 0
    captured = capsys.readouterr()
    assert "SQL_INJECTION_RISK" in captured.out
