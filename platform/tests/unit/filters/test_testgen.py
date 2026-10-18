"""`shipharness testgen` end to end with a scripted model client and a LocalSandbox on a temporary
repo written by the test (trusted code)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shipharness.config import Settings
from shipharness.events import read_events
from shipharness.runner.model import ScriptedModelClient, tool_step
from shipharness.testgen import commands
from shipharness.testgen.run import TestgenOptions, module_to_dotted, run_testgen, strip_tests

from .helpers import PY, make_repo

GENERATED = """\
from calc import clamp


def test_clamp_high():
    assert clamp(5, 0, 3) == 3


def test_vacuous():
    clamp(-1, 0, 3)
    assert True
"""


def creation_patch(path: str, text: str) -> str:
    lines = text.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def script() -> ScriptedModelClient:
    return ScriptedModelClient(
        [
            tool_step("apply_patch", patch=creation_patch("tests/test_generated.py", GENERATED)),
            tool_step("finish", claim="done", summary="wrote two tests"),
        ]
    )


def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        runs_dir=tmp_path / "state" / "runs",
        langsmith_tracing=False,
        sandbox_mode="none",
    )


def test_module_to_dotted() -> None:
    assert module_to_dotted("app/services/issues.py") == "app.services.issues"
    assert module_to_dotted("src/pkg/__init__.py") == "pkg"
    assert module_to_dotted("calc.py") == "calc"


def test_strip_tests_removes_discarded_functions_and_methods() -> None:
    source = (
        "import pytest\n\n\n@pytest.mark.slow\ndef test_a():\n    assert 1 == 1\n\n\n"
        "def test_b():\n    assert 2 == 2\n\n\nclass TestC:\n    def test_d(self):\n"
        "        assert 3 == 3\n\n    def test_e(self):\n        assert 4 == 4\n"
    )
    stripped = strip_tests(source, {"test_a", "TestC::test_d"})
    assert "test_a" not in stripped and "slow" not in stripped
    assert "def test_b" in stripped and "def test_e" in stripped and "test_d" not in stripped
    compile(stripped, "x.py", "exec")


def test_testgen_end_to_end_keeps_only_tests_that_pass_all_filters(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    options = TestgenOptions(
        repo=repo, module="calc.py", max_tests=5, python=PY, out_dir=tmp_path / "out"
    )
    result = run_testgen(options, settings(tmp_path), client=script())
    assert result.exit_code == 0, result.error
    assert result.unsandboxed is True
    assert result.kept == ["tests/test_generated.py::test_clamp_high"]
    assert result.discarded["tests/test_generated.py::test_vacuous"].filter == 4

    kept_file = tmp_path / "out" / "tests" / "test_generated.py"
    text = kept_file.read_text(encoding="utf-8")
    assert "def test_clamp_high" in text and "test_vacuous" not in text
    report = json.loads((tmp_path / "out" / "testgen-report.json").read_text(encoding="utf-8"))
    assert report["kept"] == result.kept
    assert report["unsandboxed"] is True
    assert {r["test_id"] for r in report["results"]} == {
        "tests/test_generated.py::test_clamp_high",
        "tests/test_generated.py::test_vacuous",
    }
    # The learner's repository is never modified; the agent worked in a copy.
    assert not (repo / "tests" / "test_generated.py").exists()
    types = [e.type for e in read_events(result.events_path)]
    assert types[0] == "sandbox_start" and "run_start" in types and "run_end" in types
    assert types.count("test_proposed") == 2


def test_testgen_rejects_a_module_outside_the_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    options = TestgenOptions(repo=repo, module="../calc.py", python=PY)
    result = run_testgen(options, settings(tmp_path), client=script())
    assert result.exit_code == 1
    assert "module" in (result.error or "")


def test_testgen_verify_layer_requires_the_layer_to_be_available(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    options = TestgenOptions(repo=repo, module="calc.py", layers="verify", python=PY)
    result = run_testgen(options, settings(tmp_path), client=script())
    if result.exit_code == 1:
        assert "verify" in (result.error or "")
    else:  # after integration the verify layer exists and the run completes
        assert result.exit_code == 0


def harnessed_script(test_dir: str = "tests") -> ScriptedModelClient:
    """What an agent does on a repository whose tests live in `test_dir`: write the tests, run
    them with run_visible_tests, commit, and claim done once."""
    path = f"{test_dir}/test_generated.py"
    commit = f"git add {path} && git -c user.name=t -c user.email=t@x.invalid commit -qm 'tests'"
    return ScriptedModelClient(
        [
            tool_step("apply_patch", patch=creation_patch(path, GENERATED)),
            tool_step("run_visible_tests", selector=path),
            tool_step("run", command=commit, timeout_s=None),
            tool_step("finish", claim="done", summary="wrote two tests"),
        ]
    )


def test_testgen_with_the_verify_layer_on_a_repo_that_is_not_teamtrack(tmp_path: Path) -> None:
    """The boltons worked example's defects, on a temporary repo with tests in tests/ and no
    Alembic: run_visible_tests accepts the new test file, the first gate passes (visible tests
    are tests/, the migration head check is skipped), and the report counts the two tests the
    verify layer's filters evaluated, with their reasons."""
    repo = make_repo(tmp_path / "repo")
    assert not (repo / "alembic.ini").exists()
    options = TestgenOptions(
        repo=repo,
        module="calc.py",
        layers="verify",
        max_tests=5,
        existing_tests=["tests/test_calc.py"],
        python=PY,
        out_dir=tmp_path / "out",
    )
    result = run_testgen(options, settings(tmp_path), client=harnessed_script())
    assert result.exit_code == 0, result.error
    events = list(read_events(result.events_path))

    calls = {e.data["call_id"]: e.data["name"] for e in events if e.type == "tool_call"}
    [visible] = [
        e.data
        for e in events
        if e.type == "tool_result" and calls[e.data["call_id"]] == "run_visible_tests"
    ]
    assert visible["ok"] is True, visible["output_excerpt"]
    assert visible["output_excerpt"].startswith("passed=")
    assert "failed=0 errors=0" in visible["output_excerpt"]

    gates = [e.data for e in events if e.type == "gate_result" and e.data["items"][0]["detail"]]
    assert len(gates) == 1 and gates[0]["passed"] is True, gates
    items = {i["name"]: i for i in gates[0]["items"]}
    assert items["visible tests"]["status"] == "pass"
    assert "skipped: no migrations configured" in items["clean state"]["detail"]

    assert {r.test_id for r in result.results} == {
        "tests/test_generated.py::test_clamp_high",
        "tests/test_generated.py::test_vacuous",
    }
    assert result.kept == ["tests/test_generated.py::test_clamp_high"]
    assert result.discarded["tests/test_generated.py::test_vacuous"].filter == 4
    report = json.loads((tmp_path / "out" / "testgen-report.json").read_text(encoding="utf-8"))
    assert report["kept"] == result.kept
    assert len({r["test_id"] for r in report["results"]}) == 2
    assert all(r["reason"] for r in report["results"])
    kept_file = (tmp_path / "out" / "tests" / "test_generated.py").read_text(encoding="utf-8")
    assert "def test_clamp_high" in kept_file and "test_vacuous" not in kept_file
    # The filters ran once, not once in the verify layer and again in testgen.
    assert [e.type for e in events].count("test_proposed") == 2


def test_testgen_visible_tests_dir_comes_from_the_existing_tests(tmp_path: Path) -> None:
    from shipharness.testgen.run import visible_tests_dir

    repo = make_repo(tmp_path / "repo")
    assert visible_tests_dir(repo, ["tests/test_calc.py"]) == "tests"
    assert visible_tests_dir(repo, ["tests"]) == "tests"
    assert visible_tests_dir(repo, ["tests/test_calc.py::test_add"]) == "tests"
    assert visible_tests_dir(repo, ["tests/unit/a/test_x.py", "tests/unit/test_y.py"]) == (
        "tests/unit"
    )
    assert visible_tests_dir(repo, ["tests/visible/test_issues.py"]) == "tests/visible"
    assert visible_tests_dir(repo, ["test_top.py"]) == "."
    assert visible_tests_dir(repo, []) == "tests"
    assert visible_tests_dir(tmp_path / "empty", []) == "."
    assert visible_tests_dir(repo, ["tests/test_calc.py"], explicit="checks/") == "checks"


@pytest.fixture
def cli_app() -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """Test app."""

    commands.register(app)
    return app


def test_cli_testgen_end_to_end(tmp_path: Path, cli_app: typer.Typer, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = make_repo(tmp_path / "repo")
    monkeypatch.setattr(commands, "load_settings", lambda: settings(tmp_path))
    monkeypatch.setattr(commands, "make_client", lambda _settings: script())
    args = ["testgen", "--repo", str(repo), "--module", "calc.py", "--python", PY]
    args += ["--out", str(tmp_path / "out")]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert "UNSANDBOXED" in result.output
    assert "kept 1 of 2" in result.output
    assert "test_vacuous: filter 4" in result.output
    assert result.output.strip().splitlines()[-1].startswith("Cost: $")


def test_cli_testgen_with_verify_counts_the_tests_the_layer_filtered(  # type: ignore[no-untyped-def]
    tmp_path: Path, cli_app: typer.Typer, monkeypatch
) -> None:
    """The verify layer's test-phase filters evaluate the new tests in the visible directory and
    remove the discarded ones; the summary still counts both, with the discarding filter."""
    repo = make_repo(tmp_path / "repo")
    (repo / "tests" / "visible").mkdir()
    (repo / "tests" / "test_calc.py").rename(repo / "tests" / "visible" / "test_calc.py")
    monkeypatch.setattr(commands, "load_settings", lambda: settings(tmp_path))
    monkeypatch.setattr(
        commands, "make_client", lambda _settings: harnessed_script("tests/visible")
    )
    args = ["testgen", "--repo", str(repo), "--module", "calc.py", "--python", PY]
    args += ["--tests", "tests/visible/test_calc.py", "--layers", "verify", "--max-tests", "3"]
    args += ["--out", str(tmp_path / "out")]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert "kept 1 of 2 proposed tests" in result.output
    assert "+ tests/visible/test_generated.py::test_clamp_high" in result.output
    assert "- tests/visible/test_generated.py::test_vacuous: filter 4" in result.output
    report = json.loads((tmp_path / "out" / "testgen-report.json").read_text(encoding="utf-8"))
    assert len({r["test_id"] for r in report["results"]}) == 2


def test_cli_docker_needs_an_image(tmp_path: Path, cli_app: typer.Typer, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = make_repo(tmp_path / "repo")
    monkeypatch.setattr(commands, "load_settings", lambda: settings(tmp_path))
    result = CliRunner().invoke(
        cli_app, ["testgen", "--repo", str(repo), "--module", "calc.py", "--sandbox", "docker"]
    )
    assert result.exit_code == 1
    assert "--image" in result.output
    assert result.output.strip().splitlines()[-1].startswith("Cost: $")


def test_cli_missing_openai_key(tmp_path: Path, cli_app: typer.Typer, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = make_repo(tmp_path / "repo")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(commands, "load_settings", lambda: settings(tmp_path))
    result = CliRunner().invoke(cli_app, ["testgen", "--repo", str(repo), "--module", "calc.py"])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output
