"""`shipharness init --target <dir>` and `shipharness init --check <dir>` on temporary targets."""

from __future__ import annotations

import os
import socket
import stat
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shipharness.kit.commands import register
from shipharness.kit.files import SKILL_NAMES, TEMPLATES, install, template_files
from shipharness.kit.markers import find_markers, unfilled


def make_app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """Test root."""

    register(app)
    return app


def run(*args: str) -> object:
    return CliRunner().invoke(make_app(), ["init", *args])


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any socket connection fails the test: init never calls a model or the network."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("shipharness init opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_init_writes_every_template_and_both_skill_folders(tmp_path: Path, no_network) -> None:
    result = run("--target", str(tmp_path))
    assert result.exit_code == 0, result.output
    for rel in template_files():
        assert (tmp_path / rel).read_bytes() == (TEMPLATES / rel).read_bytes(), rel
        assert f"+ {rel}\n" in result.output
    for name in SKILL_NAMES:
        for folder in (".claude/skills", ".agents/skills"):
            assert (tmp_path / folder / name / "SKILL.md").is_file()
            assert f"+ {folder}/{name}/SKILL.md\n" in result.output
    assert "0 skipped" in result.output
    assert result.output.rstrip().splitlines()[-1] == "Cost: $0.000000 (no model calls)"


def test_the_kit_holds_the_owner_listed_templates() -> None:
    files = set(template_files())
    expected = {
        "AGENTS.md",
        "ARCHITECTURE.md",
        "docs/SECURITY.md",
        "docs/RELIABILITY.md",
        "docs/QUALITY_SCORE.md",
        "docs/PLANS.md",
        "docs/design-docs/index.md",
        "docs/product-specs/index.md",
        "docs/clean-state-checklist.md",
        "docs/house-rules.md",
        "docs/exec-plans/active/F1.md",
        "feature_list.json",
        "feature_list.schema.json",
        "progress.md",
        "session-handoff.md",
        "init.sh",
        "harness/shipharness_adapter.py",
        "harness/check-params.json",
        "harness/sandbox-policy.toml",
        ".github/workflows/shipharness.yml",
    }
    assert expected <= files, sorted(expected - files)
    assert any(f.startswith("docs/references/") for f in files)


def test_init_sh_is_executable_in_the_target(tmp_path: Path) -> None:
    run("--target", str(tmp_path))
    assert (tmp_path / "init.sh").stat().st_mode & stat.S_IXUSR


def test_existing_files_are_skipped_and_listed_unless_force(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# my own map\n", encoding="utf-8")
    result = run("--target", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "# my own map\n"
    assert "! skipped AGENTS.md: exists with other content (--force overwrites)" in result.output
    assert "1 skipped" in result.output

    forced = run("--target", str(tmp_path), "--force")
    assert forced.exit_code == 0, forced.output
    assert (tmp_path / "AGENTS.md").read_bytes() == (TEMPLATES / "AGENTS.md").read_bytes()
    assert "~ overwrote AGENTS.md" in forced.output


def test_second_run_writes_nothing(tmp_path: Path) -> None:
    first = run("--target", str(tmp_path))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    second = run("--target", str(tmp_path))
    assert second.exit_code == 0, second.output
    assert "+ " not in second.output
    assert "wrote 0 files" in second.output
    assert f"{len(before)} unchanged" in second.output
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    assert sum(line.startswith("+ ") for line in first.output.splitlines()) == len(before)


@pytest.mark.parametrize(
    ("choice", "present", "absent"),
    [
        ("claude", ".claude/skills", ".agents/skills"),
        ("agents", ".agents/skills", ".claude/skills"),
    ],
)
def test_skills_option_picks_the_folder(
    tmp_path: Path, choice: str, present: str, absent: str
) -> None:
    result = run("--target", str(tmp_path), "--skills", choice)
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in (tmp_path / present).iterdir()) == sorted(SKILL_NAMES)
    assert not (tmp_path / absent).exists()


def test_unknown_skills_choice_is_an_error(tmp_path: Path) -> None:
    result = run("--target", str(tmp_path), "--skills", "cursor")
    assert result.exit_code == 1
    assert "--skills must be claude, agents, or both" in result.output
    assert list(tmp_path.iterdir()) == []


def test_missing_target_is_an_error(tmp_path: Path) -> None:
    result = run("--target", str(tmp_path / "nope"))
    assert result.exit_code == 1
    assert "target directory not found" in result.output


def test_target_and_check_are_exclusive(tmp_path: Path) -> None:
    assert run().exit_code == 1
    assert run("--target", str(tmp_path), "--check", str(tmp_path)).exit_code == 1


def test_skill_copies_leave_out_bytecode(tmp_path: Path) -> None:
    templates, skills = tmp_path / "t", tmp_path / "s"
    (templates / "docs").mkdir(parents=True)
    (templates / "docs" / "a.md").write_text("a <!-- REPLACE: x -->\n", encoding="utf-8")
    for name in SKILL_NAMES:
        (skills / name / "__pycache__").mkdir(parents=True)
        (skills / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        (skills / name / "__pycache__" / "x.pyc").write_bytes(b"\0")
    target = tmp_path / "repo"
    target.mkdir()
    report = install(target, skills="claude", templates=templates, skills_dir=skills)
    assert "docs/a.md" in report.written
    assert not list(target.rglob("__pycache__"))
    assert report.written == sorted(report.written)


def test_check_lists_every_marker_with_file_and_line(tmp_path: Path) -> None:
    run("--target", str(tmp_path))
    result = run("--check", str(tmp_path))
    assert result.exit_code == 1, result.output
    markers, missing = unfilled(tmp_path)
    assert markers and not missing
    for marker in markers[:20]:
        assert f"{marker.path}:{marker.line}: {marker.text}" in result.output
    assert f"{len(markers)} REPLACE markers left" in result.output
    assert {m.path for m in markers} == set(template_files())


def test_check_passes_when_every_marker_is_filled(tmp_path: Path) -> None:
    run("--target", str(tmp_path))
    markers, _ = unfilled(tmp_path)
    for rel in {m.path for m in markers}:
        path = tmp_path / rel
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text("".join(ln for ln in lines if not find_markers(ln)), encoding="utf-8")
    (tmp_path / "docs" / "RELIABILITY.md").unlink()
    result = run("--check", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "- docs/RELIABILITY.md: not present (deleted, or never installed)" in result.output
    assert "no REPLACE markers left" in result.output


def test_check_on_a_folder_without_the_kit_is_an_error(tmp_path: Path) -> None:
    result = run("--check", str(tmp_path))
    assert result.exit_code == 1
    assert "no kit files in" in result.output


def test_marker_forms() -> None:
    assert [m.text for m in find_markers("x <!-- REPLACE: the app name -->")] == ["the app name"]
    assert [m.text for m in find_markers("  # REPLACE: your test command")] == ["your test command"]
    assert [m.text for m in find_markers('  "_replace": "one sentence per feature",')] == [
        "one sentence per feature"
    ]
    assert find_markers("plain text with REPLACE in it") == []


def test_init_is_a_shipharness_command() -> None:
    from shipharness.cli import app

    result = CliRunner().invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "--target" in result.output and "--check" in result.output


def test_init_does_not_read_the_environment_file(tmp_path: Path, monkeypatch) -> None:
    opened: list[str] = []
    real_open = Path.open

    def spy(self: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        opened.append(os.fspath(self))
        return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", spy)
    assert run("--target", str(tmp_path)).exit_code == 0
    assert not [p for p in opened if p.endswith(".env")]
