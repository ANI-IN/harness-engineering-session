"""`shipharness skills validate <dir>` wiring through `register(app)`."""

from __future__ import annotations

from pathlib import Path

import typer
from typer.testing import CliRunner

from shipharness.skills_cli.commands import register


def make_app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """Test root."""

    register(app)
    return app


def write_skill(root: Path, name: str, text: str) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    return folder


def run(*args: str) -> object:
    return CliRunner().invoke(make_app(), ["skills", "validate", *args])


def test_valid_folder_exits_zero_and_prints_cost(tmp_path: Path) -> None:
    write_skill(tmp_path, "alpha", "---\nname: alpha\ndescription: Does a. Use for a.\n---\n")
    result = run(str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "+ alpha" in result.output
    assert "1 skill checked, 0 errors, 0 warnings" in result.output
    assert result.output.rstrip().splitlines()[-1].startswith("Cost: $0.000000")


def test_errors_exit_one(tmp_path: Path) -> None:
    write_skill(tmp_path, "beta", "---\nname: gamma\ndescription: d\n---\n")
    result = run(str(tmp_path / "beta"))
    assert result.exit_code == 1
    assert "x beta: Directory name 'beta' must match skill name 'gamma'" in result.output


def test_warnings_alone_exit_zero(tmp_path: Path) -> None:
    write_skill(tmp_path, "delta", "---\nname: delta\ndescription: d\n---\nSee `scripts/x.py`.\n")
    result = run(str(tmp_path))
    assert result.exit_code == 0
    assert "! delta: referenced file 'scripts/x.py' is missing" in result.output
    assert "0 errors, 1 warning" in result.output


def test_missing_path_exits_one(tmp_path: Path) -> None:
    result = run(str(tmp_path / "missing"))
    assert result.exit_code == 1
    assert "does not exist" in result.output
