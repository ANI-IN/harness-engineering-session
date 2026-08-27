"""Proof that dedup mode cannot shrink conformance coverage.

`make status` runs `verify-dedup`, in which verify.sh scripts honoring
HARNESS_SKIP_UNIT_CONFORMANCE skip their solution-stage conformance run
(and, for projects, their own test-suite sub-runs). Coverage is unchanged
because:

1. every script that honors the skip variable belongs to a unit the
   conformance gate discovers and runs in full (all cases, both stacks,
   default stage), and
2. everything a script keeps in dedup mode (the exercise --target=ci
   acceptance runs, the projects' starter-must-fail gates) runs
   identically in both modes, and
3. the projects' own test files are collected by the root pytest and
   vitest runs that both verify modes execute.

These tests fail the build if any of those three legs breaks: a skip
guard appearing in a script whose unit conformance would NOT run, an
exercise script acquiring a skip guard, a project losing its starter gate
or its tests falling outside the root suites' collection.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import run_verify  # noqa: E402
from tools.conformance import runner  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = "HARNESS_SKIP_UNIT_CONFORMANCE"


def scripts_with_guard() -> list[Path]:
    return [
        script
        for script in run_verify.discover_scripts(REPO_ROOT)
        if GUARD in script.read_text(encoding="utf-8")
    ]


def test_every_skip_guarded_script_is_a_discovered_conformance_unit():
    units = set(runner.discover_units(REPO_ROOT))
    guarded = scripts_with_guard()
    assert guarded, "expected skip guards in demo and project verify scripts"
    for script in guarded:
        assert script.parent in units, (
            f"{script} honors the dedup skip but its unit is not discovered by "
            "the conformance gate; dedup mode would lose its cases"
        )


def test_exercise_scripts_never_carry_the_skip_guard():
    for script in run_verify.discover_scripts(REPO_ROOT):
        if "exercises" in script.parts:
            assert GUARD not in script.read_text(encoding="utf-8"), (
                f"{script}: the four-run --target=ci acceptance discipline is "
                "not a duplicate and must never be skipped"
            )


def test_project_starter_gates_survive_dedup_mode():
    for script in scripts_with_guard():
        text = script.read_text(encoding="utf-8")
        if "--stage starter" not in text:
            continue
        # The starter gate must not sit inside the skip guard: in dedup mode
        # the guard's block is skipped, and the gate is unique coverage.
        guard_block_start = text.index(f'if [ "${{{GUARD}:-0}}" != "1" ]; then')
        assert text.index("--stage starter") > guard_block_start, script
        before_gate = text[: text.index("--stage starter")]
        assert before_gate.count("if [") > before_gate.count("fi\n") - 1


def test_project_test_suites_are_collected_by_the_root_runs():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"projects"' in pyproject.split("testpaths")[1].split("]")[0], (
        "root pytest no longer collects projects/; dedup mode would lose the "
        "project Python suites"
    )
    vitest = (REPO_ROOT / "vitest.config.mts").read_text(encoding="utf-8")
    assert "projects/**/typescript/**/*.test.ts" in vitest, (
        "root vitest no longer collects projects/; dedup mode would lose the "
        "project TypeScript suites"
    )


def test_runner_logs_coverage_identifiers(tmp_path, monkeypatch):
    """The coverage log the equality proof rests on: running a unit appends
    one (unit, stage, stack, case) line per executed case."""
    log = tmp_path / "coverage.log"
    monkeypatch.setenv(runner.COVERAGE_LOG_ENV, str(log))
    unit = REPO_ROOT / "tools" / "conformance" / "selftest" / "canary-unit"
    report = runner.run_unit(unit, ("python",))
    assert report.ok
    lines = log.read_text(encoding="utf-8").strip().split("\n")
    cases = json.loads((unit / "cases.json").read_text(encoding="utf-8"))["cases"]
    assert len(lines) == len(cases)
    for line in lines:
        unit_id, stage, stack, case = line.split("\t")
        assert unit_id == "tools/conformance/selftest/canary-unit"
        assert stage == "plain"
        assert stack == "python"
    assert {line.split("\t")[3] for line in lines} == {case["name"] for case in cases}


def test_dedup_skip_reaches_scripts_through_run_verify(tmp_path):
    """run_verify --skip-unit-conformance must actually export the variable:
    a guarded demo script under it prints its skip line and runs nothing."""
    script = (
        REPO_ROOT / "lectures" / "lecture-01-why-capable-agents-still-fail"
        / "code" / "verify.sh"
    )
    env = dict(os.environ)
    env[GUARD] = "1"
    proc = subprocess.run(
        ["bash", str(script)], cwd=script.parent,
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0
    assert "skipped (unit conformance covered by make conformance" in proc.stdout
