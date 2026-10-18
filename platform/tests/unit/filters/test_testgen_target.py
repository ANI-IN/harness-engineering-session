"""`shipharness testgen --target <id>`: the target's testgen-targets-v1 line fills the repo, module,
existing tests, mutants, and target metadata (so `baseline_includes_doctests` takes effect). Runs
with a scripted model client on temporary trusted repos: no network, no keys."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shipharness.config import Settings
from shipharness.events import read_events
from shipharness.runner.model import ScriptedModelClient, tool_step
from shipharness.testgen import commands
from shipharness.testgen.targets import TargetError, resolve_target

from .helpers import DOUBLE_TEST, MATHX, MATHX_TEST

LIB = "boltlike"
TARGET = "TG-boltlike-mathx"
MUTANTS = "datasets/mutants/boltlike/mathx.jsonl"


def _line(target_id: str, repo: str, module: str, tests: list[str], **meta: object) -> dict:
    return {
        "inputs": {
            "target_id": target_id,
            "repo": repo,
            "pin": "1.0",
            "module": module,
            "existing_tests": tests,
        },
        "outputs": {
            "filter_mutants": f"{MUTANTS}#filter",
            "referee_mutants": f"{MUTANTS}#referee",
            "known_failures": [],
        },
        "metadata": {"example_id": target_id, "license": "MIT", "commit": "abc", **meta},
        "split": ["testgen"],
    }


def _mutant(n: int, kind: str, line: int, original: str, replacement: str) -> dict:
    return {
        "id": f"mathx-m{n}",
        "target": "mathx",
        "set": kind,
        "file": "mathx.py",
        "line": line,
        "original": original,
        "replacement": replacement,
        "rationale": "wrong factor",
    }


def make_course(root: Path, *, fetched: bool = True) -> Path:
    """A course root with a fetched boltons-like library, its venv python, and a dataset."""
    lib = root / ".shipharness" / "libs" / LIB
    if fetched:
        src = lib / "src"
        (src / "tests").mkdir(parents=True)
        (src / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
        (src / "mathx.py").write_text(MATHX, encoding="utf-8")
        (src / "tests" / "test_mathx.py").write_text(MATHX_TEST, encoding="utf-8")
        venv_python = lib / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
        venv_python.chmod(0o755)
    mutants = root / MUTANTS
    mutants.parent.mkdir(parents=True)
    records = [
        _mutant(1, "filter", 11, "    return x * 3", "    return x * 4"),
        _mutant(2, "referee", 7, "    return x * 2", "    return x * 3"),
    ]
    mutants.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    (root / "teamtrack" / "app").mkdir(parents=True)
    dataset = root / "datasets" / "targets.jsonl"
    lines = [
        _line(TARGET, LIB, "mathx.py", ["tests/test_mathx.py"], baseline_includes_doctests=True),
        _line("TG-teamtrack-app-x", "teamtrack", "app/x.py", ["tests/visible/test_x.py"]),
    ]
    dataset.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return dataset


def test_a_library_target_fills_every_option_from_its_line(tmp_path: Path) -> None:
    dataset = make_course(tmp_path)
    target = resolve_target(TARGET, dataset, tmp_path)
    lib = tmp_path / ".shipharness" / "libs" / LIB
    assert target.repo == lib / "src"
    assert target.module == "mathx.py"
    assert target.existing_tests == ["tests/test_mathx.py"]
    assert target.mutants == tmp_path / MUTANTS and target.mutant_set == "filter"
    assert target.python is not None and str(lib / ".venv" / "bin" / "python") in target.python
    assert target.metadata["baseline_includes_doctests"] is True


def test_a_teamtrack_target_runs_in_teamtrack(tmp_path: Path) -> None:
    dataset = make_course(tmp_path)
    target = resolve_target("TG-teamtrack-app-x", dataset, tmp_path)
    assert target.repo == tmp_path / "teamtrack"
    assert target.module == "app/x.py" and target.python is None


def test_a_missing_library_says_how_to_fetch_it(tmp_path: Path) -> None:
    dataset = make_course(tmp_path, fetched=False)
    with pytest.raises(TargetError, match="scripts/fetch_testgen_libs.py"):
        resolve_target(TARGET, dataset, tmp_path)


def test_an_unknown_target_is_a_clear_error(tmp_path: Path) -> None:
    dataset = make_course(tmp_path)
    with pytest.raises(TargetError, match="TG-nothing"):
        resolve_target("TG-nothing", dataset, tmp_path)


def creation_patch(path: str, text: str) -> str:
    lines = text.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def script() -> ScriptedModelClient:
    return ScriptedModelClient(
        [
            tool_step("apply_patch", patch=creation_patch("tests/test_generated.py", DOUBLE_TEST)),
            tool_step("finish", claim="done", summary="wrote one test"),
        ]
    )


@pytest.fixture
def cli_app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """Test app."""

    commands.register(app)
    return app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        runs_dir=tmp_path / "state" / "runs",
        langsmith_tracing=False,
        sandbox_mode="none",
    )


@pytest.mark.skipif(os.name != "posix", reason="the fake library venv python is a shell script")
def test_cli_target_metadata_turns_doctests_on(
    tmp_path: Path, cli_app: typer.Typer, monkeypatch: pytest.MonkeyPatch
) -> None:
    course = tmp_path / "course"
    dataset = make_course(course)
    monkeypatch.setattr(commands, "COURSE_ROOT", course)
    monkeypatch.setattr(commands, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(commands, "make_client", lambda _settings: script())
    out = tmp_path / "out"
    args = ["testgen", "--target", TARGET, "--targets-file", str(dataset), "--out", str(out)]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert "Baseline: existing suite with doctests (--doctest-modules)" in result.output
    assert f"target {TARGET}" in result.output
    report = json.loads((out / "testgen-report.json").read_text(encoding="utf-8"))
    assert report["baseline_includes_doctests"] is True
    # The library's own tree is never modified; the agent worked in a copy.
    assert not (
        course / ".shipharness" / "libs" / LIB / "src" / "tests" / "test_generated.py"
    ).exists()
    runs = tmp_path / "state" / "runs"
    [events] = list(runs.glob("*/events.jsonl"))
    baseline = next(e for e in read_events(events) if e.type == "harness_decision")
    assert baseline.data["data"]["doctest_modules"] is True
    assert "mathx.py" in baseline.data["paths"]  # the module joins the suite for its doctests


def test_cli_explicit_options_override_the_target(
    tmp_path: Path, cli_app: typer.Typer, monkeypatch: pytest.MonkeyPatch
) -> None:
    course = tmp_path / "course"
    dataset = make_course(course)
    seen: list[object] = []
    monkeypatch.setattr(commands, "COURSE_ROOT", course)
    monkeypatch.setattr(commands, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(commands, "make_client", lambda _settings: script())

    def fake_run(options, settings, *, client):  # type: ignore[no-untyped-def]
        from shipharness.testgen.run import TestgenResult

        seen.append(options)
        return TestgenResult(exit_code=0, run_id="r-1", status="completed")

    monkeypatch.setattr("shipharness.testgen.run.run_testgen", fake_run)
    other = tmp_path / "other"
    other.mkdir()
    args = ["testgen", "--target", TARGET, "--targets-file", str(dataset)]
    args += ["--repo", str(other), "--module", "other.py", "--tests", "t/test_o.py"]
    args += ["--python", "python3"]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    [options] = seen
    assert options.repo == other and options.module == "other.py"  # type: ignore[attr-defined]
    assert options.existing_tests == ["t/test_o.py"] and options.python == "python3"  # type: ignore[attr-defined]
    assert options.target_metadata["baseline_includes_doctests"] is True  # type: ignore[attr-defined]


def test_cli_without_target_or_repo_and_module_is_an_error(
    tmp_path: Path, cli_app: typer.Typer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(commands, "load_settings", lambda: _settings(tmp_path))
    result = CliRunner().invoke(cli_app, ["testgen", "--module", "calc.py"])
    assert result.exit_code == 1
    assert "--target" in result.output and "--repo" in result.output
    assert result.output.strip().splitlines()[-1].startswith("Cost: $")
