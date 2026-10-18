"""Slow validation against the pinned libraries in .shipharness/libs (skipped when absent).

Fetch them first: `uv run python scripts/fetch_testgen_libs.py` (network). Library code is trusted
here: it is the pinned upstream source, run in a LocalSandbox on temporary copies.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import Settings
from shipharness.filters.mutants import Mutant, load_mutants, run_mutant_detailed
from shipharness.runner.model import ScriptedModelClient, tool_step
from shipharness.sandbox import LocalSandbox, default_policy
from shipharness.testgen.run import TestgenOptions, run_testgen

from .testgen_support import LIBRARIES, MUTANTS, REPO, VALIDATION, committed_lines, load_script

pytestmark = pytest.mark.slow

FETCH = load_script("fetch_testgen_libs")


def _ready(name: str) -> bool:
    try:
        return not FETCH.check(FETCH.LIBS[name])
    except (OSError, RuntimeError):
        return False


def require(name: str) -> None:
    if not _ready(name):
        pytest.skip(f"{name} is not fetched: uv run python scripts/fetch_testgen_libs.py")


def python_cmd(name: str) -> str:
    return f'"{FETCH.venv_python(name)}"'


def sandbox(workspace: Path) -> LocalSandbox:
    return LocalSandbox(default_policy(Settings(_env_file=None)), workspace, None, "r-test", "bare")


@pytest.fixture(scope="module")
def record() -> dict[str, Any]:
    return json.loads(VALIDATION.read_text(encoding="utf-8"))


def source_copy(name: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp(name) / "src"
    shutil.copytree(
        FETCH.source_dir(name), dest, ignore=shutil.ignore_patterns(".git", "__pycache__")
    )
    return dest


@pytest.mark.parametrize("name", LIBRARIES)
def test_every_mutant_applies_to_the_pinned_source(name: str) -> None:
    require(name)
    for path in sorted((MUTANTS / name).glob("*.jsonl")):
        load_mutants(path, FETCH.source_dir(name))  # raises if an `original` does not match


@pytest.mark.parametrize("name", LIBRARIES)
def test_dataset_existing_tests_exist_in_the_pinned_source(name: str) -> None:
    require(name)
    src = FETCH.source_dir(name)
    for line in committed_lines():
        if line["inputs"]["repo"] == name:
            assert (src / line["inputs"]["module"]).is_file()
            for test in line["inputs"]["existing_tests"]:
                assert (src / test.split("::", 1)[0]).exists(), test


@pytest.mark.parametrize("name", LIBRARIES)
def test_recorded_killers_pass_on_the_pinned_source_and_kill_their_mutant(
    name: str, record: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> None:
    require(name)
    work = source_copy(name, tmp_path_factory)
    mutants = [
        m for path in sorted((MUTANTS / name).glob("*.jsonl")) for m in load_mutants(path, work)
    ]
    killers = sorted({record["mutants"][m.id]["killed_by"] for m in mutants})
    baseline = subprocess.run(
        [str(FETCH.venv_python(name)), "-m", "pytest", "-q", "-p", "no:cacheprovider", *killers],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert baseline.returncode == 0, baseline.stdout[-2000:]

    def run(m: Mutant) -> tuple[Mutant, str, str]:
        killer = record["mutants"][m.id]["killed_by"]
        result = run_mutant_detailed(m, [killer], work, sandbox(work), 300, python=python_cmd(name))
        return m, result.outcome, result.killed_by or result.detail

    workers = max(2, min(8, os.cpu_count() or 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(run, mutants))
    not_killed = [
        f"{m.id}: {outcome}: {detail}" for m, outcome, detail in outcomes if outcome != "killed"
    ]
    assert not not_killed, "\n".join(not_killed)
    for m, _, killed_by in outcomes:
        # A parametrized node id with spaces is not parsed back from pytest's summary line.
        if "::" in killed_by:
            assert killed_by.startswith(record["mutants"][m.id]["killed_by"])


GENERATED = """\
from boltons.mathutils import ceil, floor


def test_ceil_picks_the_smallest_option_at_or_above():
    assert ceil(3.5, [1, 3, 4, 7]) == 4
    assert ceil(4, [1, 3, 4, 7]) == 4


def test_floor_picks_the_largest_option_at_or_below():
    assert floor(3.5, [1, 3, 4, 7]) == 3
    assert floor(4, [1, 3, 4, 7]) == 4
"""


def creation_patch(path: str, text: str) -> str:
    lines = text.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def test_testgen_runs_on_a_boltons_target_with_a_scripted_model(tmp_path: Path) -> None:
    require("boltons")
    line = next(x for x in committed_lines() if x["inputs"]["target_id"] == "TG-boltons-mathutils")
    ref = line["outputs"]["filter_mutants"].partition("#")[0]
    client = ScriptedModelClient(
        [
            tool_step(
                "apply_patch",
                patch=creation_patch("tests/test_mathutils_generated.py", GENERATED),
            ),
            tool_step("finish", claim="done", summary="wrote two tests"),
        ]
    )
    settings = Settings(
        _env_file=None,
        runs_dir=tmp_path / "state" / "runs",
        langsmith_tracing=False,
        sandbox_mode="none",
    )
    options = TestgenOptions(
        repo=FETCH.source_dir("boltons"),
        module=line["inputs"]["module"],
        max_tests=5,
        existing_tests=line["inputs"]["existing_tests"],
        mutants=REPO / ref,
        python=python_cmd("boltons"),
        out_dir=tmp_path / "out",
    )
    result = run_testgen(options, settings, client=client)
    assert result.exit_code == 0, result.error
    assert {r.test_id for r in result.results} == {
        "tests/test_mathutils_generated.py::test_ceil_picks_the_smallest_option_at_or_above",
        "tests/test_mathutils_generated.py::test_floor_picks_the_largest_option_at_or_below",
    }
    report = json.loads((tmp_path / "out" / "testgen-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert not FETCH.check(FETCH.LIBS["boltons"])  # the pinned clone was not modified
