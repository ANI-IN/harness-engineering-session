"""Doctests in the baseline suite: with `doctest_modules`, the baseline coverage run
and every existing-suite run pass `--doctest-modules`, so a doctest counts like an existing test.
Generated candidate tests still run as ordinary test ids."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shipharness.config import Settings
from shipharness.events import read_events
from shipharness.filters.coverage import measure_coverage
from shipharness.filters.filters import (
    AddsCoverageOrKillsMutant,
    ImportsAndRuns,
    PassesFiveRuns,
    surviving_mutants,
)
from shipharness.filters.models import CandidateTest, CoverageMap, FilterContext
from shipharness.filters.mutants import Mutant, run_mutant, run_mutant_detailed
from shipharness.filters.pipeline import build_context, collect_candidates, discarded, run_pipeline
from shipharness.filters.pytest_cmd import DOCTEST_FLAG, UnsafeTestId, pytest_command
from shipharness.runner.model import ScriptedModelClient, tool_step
from shipharness.sandbox import FakeSandbox
from shipharness.testgen import commands
from shipharness.testgen.run import (
    TestgenOptions,
    baseline_doctests,
    baseline_tests,
    run_testgen,
)

from .helpers import DOUBLE_TEST, PY, local_sandbox, make_doctest_repo

EXISTING = ["tests/test_mathx.py", "mathx.py"]
DOUBLE_ID = "tests/test_double.py::test_double"


def double_mutant() -> Mutant:
    return Mutant(
        id="mathx-m1",
        target="mathx",
        set="filter",
        file="mathx.py",
        line=7,
        original="    return x * 2",
        replacement="    return x * 3",
        rationale="wrong factor",
    )


def test_pytest_command_adds_the_doctest_flag_only_when_asked() -> None:
    plain = pytest_command("python", ["tests/test_a.py"])
    assert DOCTEST_FLAG == "--doctest-modules"
    assert DOCTEST_FLAG not in plain
    with_doctests = pytest_command("python", ["tests/test_a.py"], doctest_modules=True)
    assert with_doctests == plain.replace(' "tests', f' {DOCTEST_FLAG} "tests')
    with pytest.raises(UnsafeTestId):
        pytest_command("python", ["a.py; rm -rf x"], doctest_modules=True)


def test_filter_context_defaults_to_no_doctests(tmp_path: Path) -> None:
    ctx = FilterContext(
        workspace=tmp_path,
        sandbox=FakeSandbox(),
        baseline_coverage=CoverageMap(),
        filter_mutants=[],
        source_shas_at_phase_start={},
    )
    assert ctx.doctest_modules is False


def test_baseline_coverage_counts_doctest_lines_only_with_the_option(tmp_path: Path) -> None:
    repo = make_doctest_repo(tmp_path / "repo")
    sandbox = local_sandbox(repo)
    off = measure_coverage(repo, sandbox, EXISTING, python=PY)
    on = measure_coverage(repo, sandbox, EXISTING, python=PY, doctest_modules=True)
    assert off.ok and on.ok, (off.detail, on.detail)
    assert 7 not in off.coverage.lines("mathx.py")
    assert 7 in on.coverage.lines("mathx.py")


def _run_double_candidate(repo: Path, *, doctest_modules: bool) -> tuple[FilterContext, list]:
    sandbox = local_sandbox(repo)
    ctx = build_context(
        repo,
        sandbox,
        existing_tests=EXISTING,
        mutants=[double_mutant()],
        target_module="mathx",
        python=PY,
        doctest_modules=doctest_modules,
    )
    (repo / "tests" / "test_double.py").write_text(DOUBLE_TEST, encoding="utf-8")
    cands = collect_candidates(repo, ["tests/test_double.py"])
    assert [c.test_id for c in cands] == [DOUBLE_ID]
    return ctx, run_pipeline(cands, ctx, None)


def test_with_doctests_a_test_covering_only_a_doctested_function_is_discarded(
    tmp_path: Path,
) -> None:
    repo = make_doctest_repo(tmp_path / "repo")
    ctx, results = _run_double_candidate(repo, doctest_modules=True)
    assert ctx.doctest_modules is True
    assert 7 in ctx.baseline_coverage.lines("mathx.py")
    # The doctest kills the mutant, so it is not a survivor filter 3 could use.
    assert ctx.surviving_mutant_ids == frozenset()
    outcome = run_mutant(double_mutant(), EXISTING, repo, ctx.sandbox, 120, python=PY)
    assert outcome == "survived"  # without the flag the doctest does not run
    detailed = run_mutant_detailed(
        double_mutant(), EXISTING, repo, ctx.sandbox, 120, python=PY, doctest_modules=True
    )
    assert detailed.outcome == "killed"
    assert "mathx.py" in (detailed.killed_by or "")
    rejected = discarded(results)[DOUBLE_ID]
    assert rejected.filter == 3
    assert "adds no line coverage" in rejected.reason


def test_without_doctests_the_same_test_adds_coverage_and_the_mutant_survives(
    tmp_path: Path,
) -> None:
    repo = make_doctest_repo(tmp_path / "repo")
    ctx, results = _run_double_candidate(repo, doctest_modules=False)
    assert ctx.doctest_modules is False
    assert 7 not in ctx.baseline_coverage.lines("mathx.py")
    assert ctx.surviving_mutant_ids == frozenset({"mathx-m1"})
    third = [r for r in results if r.filter == 3]
    assert len(third) == 1 and third[0].passed, results
    assert "mathx.py:7" in third[0].reason


def test_candidate_runs_never_get_the_doctest_flag_but_existing_suite_runs_do(
    tmp_path: Path,
) -> None:
    make_doctest_repo(tmp_path)
    sandbox = FakeSandbox()
    ctx = FilterContext(
        workspace=tmp_path,
        sandbox=sandbox,
        baseline_coverage=CoverageMap(),
        filter_mutants=[double_mutant()],
        source_shas_at_phase_start={},
        existing_tests=EXISTING,
        python="python",
        runs=1,
        doctest_modules=True,
    )
    cand = CandidateTest(test_id=DOUBLE_ID, file="tests/test_double.py", source=DOUBLE_TEST)
    for flt in (ImportsAndRuns(), PassesFiveRuns(), AddsCoverageOrKillsMutant()):
        flt.evaluate(cand, ctx)
    candidate_cmds = [c for c in sandbox.commands if DOUBLE_ID in c]
    existing_cmds = [c for c in sandbox.commands if '"tests/test_mathx.py"' in c]
    assert candidate_cmds and existing_cmds
    assert all(DOCTEST_FLAG not in c for c in candidate_cmds)
    assert all(DOCTEST_FLAG in c for c in existing_cmds)
    sandbox.commands.clear()
    surviving_mutants(ctx.model_copy(update={"doctest_modules": False}))
    assert sandbox.commands and all(DOCTEST_FLAG not in c for c in sandbox.commands)


# --- testgen ---------------------------------------------------------------------------------


def test_baseline_doctests_honours_dataset_metadata_over_the_flag(tmp_path: Path) -> None:
    def opts(**kw: object) -> TestgenOptions:
        return TestgenOptions(repo=tmp_path, module="mathx.py", **kw)  # type: ignore[arg-type]

    assert baseline_doctests(opts()) is False
    assert baseline_doctests(opts(doctest_modules=True)) is True
    meta = {"baseline_includes_doctests": True}
    assert baseline_doctests(opts(target_metadata=meta)) is True
    off = {"baseline_includes_doctests": False}
    assert baseline_doctests(opts(doctest_modules=True, target_metadata=off)) is False
    assert baseline_doctests(opts(doctest_modules=True, target_metadata={"x": 1})) is True


def test_baseline_tests_adds_the_module_so_its_doctests_are_collected() -> None:
    assert baseline_tests(["tests/test_mathx.py"], "mathx.py", True) == EXISTING
    assert baseline_tests(["tests/test_mathx.py"], "mathx.py", False) == ["tests/test_mathx.py"]
    assert baseline_tests(EXISTING, "mathx.py", True) == EXISTING
    assert baseline_tests([], "mathx.py", True) == []  # the configured suite: pytest decides


def _creation_patch(path: str, text: str) -> str:
    lines = text.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def _script() -> ScriptedModelClient:
    return ScriptedModelClient(
        [
            tool_step("apply_patch", patch=_creation_patch("tests/test_generated.py", DOUBLE_TEST)),
            tool_step("finish", claim="done", summary="wrote one test"),
        ]
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        runs_dir=tmp_path / "state" / "runs",
        langsmith_tracing=False,
        sandbox_mode="none",
    )


@pytest.mark.parametrize("doctests", [True, False])
def test_testgen_doctest_option_decides_filter_3(tmp_path: Path, doctests: bool) -> None:
    repo = make_doctest_repo(tmp_path / "repo")
    options = TestgenOptions(
        repo=repo,
        module="mathx.py",
        existing_tests=["tests/test_mathx.py"],
        python=PY,
        out_dir=tmp_path / "out",
        doctest_modules=doctests,
    )
    result = run_testgen(options, _settings(tmp_path), client=_script())
    assert result.exit_code == 0, result.error
    assert result.baseline_includes_doctests is doctests
    test_id = "tests/test_generated.py::test_double"
    if doctests:
        assert result.kept == []
        assert result.discarded[test_id].filter == 3
    else:
        assert result.kept == [test_id]
    report = json.loads((tmp_path / "out" / "testgen-report.json").read_text(encoding="utf-8"))
    assert report["baseline_includes_doctests"] is doctests
    decisions = [
        e.data
        for e in read_events(result.events_path)
        if e.type == "harness_decision" and e.data["kind"] == "baseline"
    ]
    assert len(decisions) == 1
    assert decisions[0]["layer"] == "testgen"
    assert decisions[0]["data"]["doctest_modules"] is doctests
    assert ("--doctest-modules" in decisions[0]["message"]) is doctests


@pytest.fixture
def cli_app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """Test app."""

    commands.register(app)
    return app


def test_cli_doctest_modules_flag(tmp_path: Path, cli_app: typer.Typer, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = make_doctest_repo(tmp_path / "repo")
    monkeypatch.setattr(commands, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(commands, "make_client", lambda _settings: _script())
    args = ["testgen", "--repo", str(repo), "--module", "mathx.py", "--python", PY]
    args += ["--tests", "tests/test_mathx.py", "--out", str(tmp_path / "out"), "--doctest-modules"]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert "Baseline: existing suite with doctests (--doctest-modules)" in result.output
    assert "kept 0 of 1" in result.output
    assert "test_double: filter 3" in result.output


def test_cli_doctests_default_off(tmp_path: Path, cli_app: typer.Typer, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = make_doctest_repo(tmp_path / "repo")
    monkeypatch.setattr(commands, "load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(commands, "make_client", lambda _settings: _script())
    args = ["testgen", "--repo", str(repo), "--module", "mathx.py", "--python", PY]
    args += ["--out", str(tmp_path / "out")]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert "Baseline: existing suite without doctests" in result.output
    assert "kept 1 of 1" in result.output
