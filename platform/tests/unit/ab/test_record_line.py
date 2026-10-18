"""The per-arm line `shipharness ab` prints reads in plain words ("House rule 1: Tenant isolation,
new violations: 0"), not as `primary={"r1_new_violations": 0}`; the ScoreRecord export keeps the
machine field names."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from shipharness.ab.commands import record_line
from shipharness.console.labels import measure_words
from shipharness.layout import find_repo_root
from tests.unit.ab.score_fixtures import record
from tests.unit.ab.test_commands import env  # noqa: F401 - a fixture

REPO = find_repo_root(Path(__file__))


def test_the_primary_measure_reads_in_plain_words() -> None:
    assert (
        measure_words({"r1_new_violations": 0})
        == "House rule 1: Tenant isolation, new violations: 0"
    )
    assert measure_words({"continuity_failure": False}) == "continuity failure: no"
    assert (
        measure_words({"hidden_passed": 68, "mutants_killed": 4})
        == "hidden tests passed: 68; mutants killed: 4"
    )
    assert measure_words({}) == "no primary measure"


def test_the_arm_line_has_no_machine_field_names() -> None:
    line = record_line(
        record(
            arm="harness",
            claim="done",
            reviewer_verdict="accept",
            hidden_passed=50,
            hidden_total=52,
        )
    )
    assert line.startswith("  harness  completed ")
    assert "House rule 1: Tenant isolation, new violations: 0" in line
    assert "agent said: done ·" in line
    assert "primary measure passed" in line
    assert "hidden tests 50 of 52" in line and "mutants killed 2 of 4" in line
    assert "reviewer accept" in line and "cost $0.0500" in line
    for machine in ("primary=", "passed=", "claim=", "reviewer=", "cost=", "{", "_"):
        assert machine not in line, machine


@pytest.mark.parametrize(
    ("claim", "reviewer", "passed", "words"),
    [
        (
            "not_done",
            None,
            False,
            ("agent said: not done", "reviewer not run", "primary measure failed"),
        ),
        (
            "none",
            "reject",
            True,
            ("agent said: no claim", "reviewer reject", "primary measure passed"),
        ),
    ],
)
def test_claims_and_reviewer_read_plainly(
    claim: str, reviewer: str | None, passed: bool, words: tuple[str, ...]
) -> None:
    line = record_line(record(claim=claim, reviewer_verdict=reviewer, passed_primary=passed))
    for text in words:
        assert text in line


def test_the_score_export_keeps_the_machine_field_names() -> None:
    data = json.loads(record().model_dump_json())
    assert data["primary"] == {"r1_new_violations": 0}
    assert data["passed_primary"] is True and data["claim"] == "done"


def _a4_live():  # type: ignore[no-untyped-def]
    path = REPO / "section-4-verification" / "assignment" / "visible_tests" / "a4_live.py"
    spec = importlib.util.spec_from_file_location("a4_live_for_record_line", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_assignment_4_check_reads_the_new_and_the_old_arm_line() -> None:
    pattern: re.Pattern[str] = _a4_live().AB_RECORD
    new = record_line(record(arm="harness", status="ABORTED: timeout"))
    old = "  bare     completed         claim=done     primary={} passed=True hidden 1/1"
    assert pattern.match(new).groups() == ("harness", "ABORTED: timeout")  # type: ignore[union-attr]
    phases = record_line(record(arm="harness"), {"build": "done", "test": "not_done"})
    assert pattern.match(phases).groups() == ("harness", "completed")  # type: ignore[union-attr]
    plain = "  bare     completed         agent said done · no primary measure"  # 2026-10-18
    assert pattern.match(plain).groups() == ("bare", "completed")  # type: ignore[union-attr]
    assert pattern.match(old).groups() == ("bare", "completed")  # type: ignore[union-attr]


def test_the_cli_prints_the_plain_arm_line_and_the_final_announces_its_feature(env) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    from typer.testing import CliRunner

    from .test_commands import make_app

    args = ["ab", "--feature", "org-search", "--section", "final", "--no-preview",
            "--dataset", str(env.dataset)]  # fmt: skip
    result = CliRunner().invoke(make_app(), args)
    lines = result.output.splitlines()
    assert lines[0] == "Final A/B: Feature 1: Org-wide issue search"
    arm_lines = [line for line in lines if line.startswith(("  bare ", "  harness "))]
    assert len(arm_lines) == 2
    assert all("agent said: " in line and "primary=" not in line for line in arm_lines)


def test_a_feature_without_a_primary_measure_shows_no_verdict() -> None:
    line = record_line(record(primary={}, passed_primary=True))
    assert "no primary measure · hidden tests" in line and "primary measure passed" not in line
