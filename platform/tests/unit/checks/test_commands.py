"""`shipharness check` (registered by shipharness.checks.commands.register)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shipharness.checks.commands import register


@pytest.fixture
def app() -> typer.Typer:
    cli = typer.Typer()

    @cli.callback()
    def main() -> None:
        """Test CLI."""

    register(cli)
    return cli


def test_check_passes_with_exit_0_and_prints_cost(app: typer.Typer, base_build: Path) -> None:
    result = CliRunner().invoke(app, ["check", "--app", str(base_build), "--rules", "R6,R7"])
    assert result.exit_code == 0, result.output
    assert "r6_layering" in result.stdout and "PASS" in result.stdout
    assert "House rule 6: Layering" in result.stdout and "House rule 7: Migrations" in result.stdout
    assert "Cost: $0.000000 (no model calls)" in result.stdout
    assert "UNSANDBOXED" in result.output


def test_check_new_violations_exit_3_and_list_findings(app: typer.Typer, base_build: Path) -> None:
    result = CliRunner().invoke(app, ["check", "--app", str(base_build), "--rules", "R1"])
    assert result.exit_code == 3, result.output
    assert "GET /v1/issues" in result.stdout


def test_check_json_output_is_one_document(app: typer.Typer, base_build: Path) -> None:
    result = CliRunner().invoke(app, ["check", "--app", str(base_build), "--rules", "R6", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert [r["check"] for r in data["results"]] == ["r6_layering"]


def test_check_with_baseline_counts_only_new(
    app: typer.Typer, base_build: Path, tmp_path: Path
) -> None:
    first = CliRunner().invoke(app, ["check", "--app", str(base_build), "--rules", "R1", "--json"])
    baseline = tmp_path / "baseline.json"
    baseline.write_text(first.stdout, encoding="utf-8")
    again = CliRunner().invoke(
        app, ["check", "--app", str(base_build), "--rules", "R1", "--baseline", str(baseline)]
    )
    assert again.exit_code == 0, again.output


def test_check_unknown_rule_exits_1(app: typer.Typer, base_build: Path) -> None:
    result = CliRunner().invoke(app, ["check", "--app", str(base_build), "--rules", "R42"])
    assert result.exit_code == 1
    assert "unknown check" in result.output
