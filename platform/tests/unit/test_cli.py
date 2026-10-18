import subprocess
from pathlib import Path

from typer.testing import CliRunner

from shipharness import __version__, freeze
from shipharness.cli import app
from shipharness.config import Settings
from tests.unit.cli_output import strip_ansi

MODULE_TITLE = "Module 1: Harness Engineering for Coding Agents"


def test_version_flag_prints_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_header_is_the_module_title() -> None:
    # Module 1 of a multi-module program; the CLI help header carries the title.
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    lines = [line.strip(" │") for line in strip_ansi(result.output).splitlines()]
    text = [line for line in lines if line and not line.startswith("Usage:")]
    assert text[0] == MODULE_TITLE
    assert "Harness engineering for coding agents." not in result.output


def test_help_names_the_readable_feature_names() -> None:
    from shipharness.datasets.names import FEATURE_ALIASES

    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    text = " ".join(line.strip(" │") for line in strip_ansi(result.output).splitlines())
    text = " ".join(text.split())
    for code, alias in FEATURE_ALIASES.items():
        assert f"{alias} ({code})" in text, alias


def test_no_args_shows_the_module_title() -> None:
    result = CliRunner().invoke(app, [])
    assert MODULE_TITLE in strip_ansi(result.output)


def _git(repo: Path, *args: str) -> None:
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
    subprocess.run(["git", *ident, *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: Path, *, tagged: bool) -> Path:
    repo = tmp_path / "copy"
    (repo / "platform" / "datasets").mkdir(parents=True)
    (repo / "platform" / "datasets" / "features.jsonl").write_text("{}\n", encoding="utf-8")
    (repo / "platform" / "teamtrack").mkdir()
    (repo / "platform" / "teamtrack" / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "class")
    _git(repo, "tag", "m1-s1-start")
    _git(repo, "tag", "m1-s2-start")
    if tagged:
        record = freeze.class_record(repo, Settings(_env_file=None))
        freeze.write_class_tag(repo, record, identity=("t", "t@t"))
    return repo


def test_verify_reports_a_matching_copy(tmp_path: Path) -> None:
    repo = _repo(tmp_path, tagged=True)
    result = CliRunner().invoke(app, ["verify", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    n = len(freeze.FROZEN_PATHS)
    assert result.output.strip() == f"your copy matches class-v1: {n} paths, 2 checkpoint trees"


def test_verify_lists_one_line_per_difference(tmp_path: Path) -> None:
    repo = _repo(tmp_path, tagged=True)
    (repo / "platform" / "datasets" / "features.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    (repo / "platform" / "teamtrack" / "app.py").write_text("x = 2\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "edit")
    _git(repo, "tag", "-f", "m1-s1-start")
    result = CliRunner().invoke(app, ["verify", "--tag", "class-v1", "--repo", str(repo)])
    assert result.exit_code == 1
    assert result.output.splitlines() == [
        "content differs: platform/datasets",
        "checkpoint content differs: m1-s1-start",
    ]


def test_verify_without_the_tag_says_to_fetch_tags(tmp_path: Path) -> None:
    repo = _repo(tmp_path, tagged=False)
    result = CliRunner().invoke(app, ["verify", "--repo", str(repo)])
    assert result.exit_code == 2
    assert "git fetch --tags" in result.output
