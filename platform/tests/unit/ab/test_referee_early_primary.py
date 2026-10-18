"""Early primary verdict: for each arm the referee runs the checks the task's primary measure reads
first, emits `primary_verdict`, then runs the rest. The final ScoreRecord must not change.

The expectations file was written by the referee as it was before this change (one runner call
for every check, then the mutants), judging the same scenarios; both orders must reproduce it.
"""

from __future__ import annotations

import json
import shlex
import time
from pathlib import Path
from typing import Any

import pytest

from shipharness.ab.referee import REFEREE_CHECKS, Referee, RefereeTask, primary_stage
from shipharness.ab.score import ScoreRecord, primary_fields
from shipharness.events import EventBus, read_events
from shipharness.reviewer import Review, ReviewOutcome
from shipharness.sandbox import ExecResult, FakeSandbox

from ..verify.fakes import runner_output
from .test_referee import OUT_OF_SCOPE, PRODUCT, all_green, deps, result

EXPECTED = Path(__file__).with_name("referee_records_before_early_primary.json")

# The pre-registered primary measures (teamtrack/reference/*/task.toml). F5-F7 and the controls
# have none; "F5" stands for all of them.
MEASURES = {
    "F1": "r1_new_violations>=1",
    "F2": "continuity_failure",
    "F3": "out_of_scope_files>=1 or test_phase_source_edits>=1",
    "F4": "hidden_passed,mutants_killed",
    "F5": "",
}
CASES = ("green", "red", "broken_diff", "runner_down", "secondary_down")
SCENARIOS = [f"{feature}-{case}" for feature in MEASURES for case in CASES]
# Not scored: when the record was written, the commit of the test's own course repo (it changes
# with every fixture repo), and the referee version stamp.
# Run metadata, not scored: single_arm marks a "harness in action" run (make show-N).
UNSCORED = {"captured_at", "checkpoint_sha", "referee_version", "single_arm", "constructed"}

LEAK = {"rule": "R1", "severity": "leak", "endpoint": "GET /a", "detail": "x", "baseline": False}


def red_results() -> list[dict[str, Any]]:
    failing = {"new_violations": 1, "passed": False}
    findings = [LEAK, {**LEAK, "severity": "violation"}]
    return all_green(
        r1_tenant={"new_violations": 2, "passed": False, "findings": findings},
        hidden_tests=failing,
        continuity=failing,
        flakiness=failing,
        board=failing,
        r6_layering=failing,
    )


def requested(command: str) -> list[str]:
    argv = shlex.split(command)
    return argv[argv.index("--checks") + 1].split(",")


class StagedFactory:
    """Referee containers whose check runner answers only the checks it was asked for (as the
    real runner does). `down`: every runner call fails; `secondary_down`: a call that includes
    the board check fails. Records the order of runner calls and mutant runs."""

    def __init__(self, results: list[dict[str, Any]], *, down: bool, secondary_down: bool) -> None:
        self.results = results
        self.down, self.secondary_down = down, secondary_down
        self.order: list[tuple[str, Any]] = []
        self.arm_box: FakeSandbox | None = None
        self.boxes = 0

    def _exec(self, command: str) -> ExecResult:
        if "checks.runner" in command:
            names = requested(command)
            self.order.append(("runner", tuple(names)))
            if self.down or (self.secondary_down and "board" in names and self.boxes > 1):
                return ExecResult(exit_code=1, output="Traceback\n", duration_ms=1)
            found = [r for r in self.results if r["check"] in names]
            return ExecResult(
                exit_code=0, output=runner_output(found, command=command), duration_ms=1
            )
        if "-m pytest" in command:
            return ExecResult(exit_code=0, output="1 passed in 0.1s\n", duration_ms=1)
        return ExecResult(exit_code=0, output="", duration_ms=1)

    def __call__(self, build: Path, mounts: list[Any], arm: str) -> FakeSandbox:
        self.boxes += 1  # the first container is the baseline's
        box = FakeSandbox(self._exec)
        if self.boxes > 1:
            self.arm_box = box
        return box


def scenario(name: str) -> dict[str, Any]:
    feature, case = name.split("-", 1)
    red = case in ("red", "secondary_down")
    diff = PRODUCT + OUT_OF_SCOPE if red else PRODUCT
    if case == "broken_diff":
        diff = PRODUCT.replace(" def list_issues():", " def list_things():")
    return {
        "measure": MEASURES[feature],
        "results": red_results() if red else all_green(),
        "diff": diff,
        "test_phase_files": ["app/api/issues.py", "tests/visible/test_issues_new.py"]
        if red
        else ["tests/visible/test_issues_new.py"],
        "down": case == "runner_down",
        "secondary_down": case == "secondary_down",
        "green": case == "green",
    }


def run_scenario(
    name: str, course_repo: Path, tmp_path: Path, **extra: Any
) -> tuple[Any, list[Any], StagedFactory]:
    """Judge one scenario; `extra` goes to RefereeDeps (early_primary) or judge (arm_ended,
    recorded)."""
    spec = scenario(name)
    factory = StagedFactory(
        spec["results"], down=spec["down"], secondary_down=spec["secondary_down"]
    )

    def mutant_runner(mutant, tests, build, sandbox):  # type: ignore[no-untyped-def]
        factory.order.append(("mutant", mutant["id"]))
        return "killed" if spec["green"] or mutant["id"] == "m1" else "survived"

    def reviewer(inp):  # type: ignore[no-untyped-def]
        review = Review(findings=[], tenant_isolation_risk="none", verdict="accept", summary="ok")
        return ReviewOutcome(review=review, status="ok", cost_usd=0.004)

    judge_kw = {k: extra.pop(k) for k in ("arm_ended", "recorded") if k in extra}
    d = deps(
        course_repo,
        tmp_path,
        factory,
        mutants=[{"id": "m1"}, {"id": "m2"}],
        mutant_runner=mutant_runner,
        reviewer=reviewer,
        **extra,
    )
    t = RefereeTask(
        feature_id=name.split("-", 1)[0],
        checkpoint="m1-s1-start",
        ticket_text="Add cursor pagination to the issue list.",
        hidden_test_ids=["teamtrack/tests/hidden/f1/test_secret.py::test_secret"],
        allowed_paths={
            "build": ["app/api/issues.py", "tests/visible/**"],
            "test": ["tests/visible/**"],
        },
        primary_measure=spec["measure"],
    )
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        verdict = Referee(t, d).judge(
            run_id="r-1",
            ab_id="ab-1",
            arm="harness",
            layers=["instructions"],
            result=result(),
            diff=spec["diff"].encode(),
            bus=bus,
            test_phase_files=spec["test_phase_files"],
            **judge_kw,
        )
    return verdict, list(read_events(log)), factory


def scored(record: ScoreRecord) -> dict[str, Any]:
    return {k: v for k, v in record.model_dump(mode="json").items() if k not in UNSCORED}


def outcome(verdict: Any) -> dict[str, Any]:
    """What the expectations file holds per scenario."""
    return {
        "record": scored(verdict.record),
        "results": [r.model_dump(mode="json")["check"] for r in verdict.results],
    }


@pytest.fixture(scope="module")
def expected() -> dict[str, Any]:
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


def test_expectations_cover_every_scenario(expected: dict[str, Any]) -> None:
    assert sorted(expected) == sorted(SCENARIOS)


@pytest.mark.parametrize("early", [True, False], ids=["early-primary", "one-call"])
@pytest.mark.parametrize("name", SCENARIOS)
def test_final_record_is_unchanged_in_either_order(
    name: str, early: bool, expected: dict[str, Any], course_repo: Path, tmp_path: Path
) -> None:
    verdict, _events, _factory = run_scenario(name, course_repo, tmp_path, early_primary=early)
    assert outcome(verdict) == expected[name]


@pytest.mark.parametrize("name", SCENARIOS)
def test_both_orders_agree_on_every_field(name: str, course_repo: Path, tmp_path: Path) -> None:
    early, _e, _f = run_scenario(name, course_repo, tmp_path / "early", early_primary=True)
    once, _e, _f = run_scenario(name, course_repo, tmp_path / "once", early_primary=False)
    skip = {"captured_at"}
    a, b = early.record.model_dump(mode="json"), once.record.model_dump(mode="json")
    assert {k: v for k, v in a.items() if k not in skip} == {
        k: v for k, v in b.items() if k not in skip
    }
    assert [r.model_dump(mode="json") for r in early.results] == [
        r.model_dump(mode="json") for r in once.results
    ]


# The referee fails after the primary verdict went out: the secondary runner call fails, or (when
# the primary measure needs no check) the only runner call does. The final record says "could not
# judge", as before, and supersedes the primary verdict.
LATE_FAILURES = [
    s
    for s in SCENARIOS
    if s.endswith("secondary_down") or s in ("F3-runner_down", "F5-runner_down")
]


@pytest.mark.parametrize("name", [s for s in SCENARIOS if s not in LATE_FAILURES])
def test_primary_verdict_matches_the_final_record(
    name: str, course_repo: Path, tmp_path: Path
) -> None:
    verdict, events, _f = run_scenario(name, course_repo, tmp_path)
    [early] = [e for e in events if e.type == "primary_verdict"]
    [final] = [e for e in events if e.type == "verdict"]
    assert early.seq < final.seq
    assert early.data["passed"] == verdict.record.passed_primary == final.data["passed_primary"]
    assert early.data["values"] == verdict.record.primary == final.data["primary"]
    assert early.data["arm"] == early.arm == "harness"
    assert early.data["run_id"] == early.run_id == "r-1"
    assert early.data["feature_id"] == name.split("-", 1)[0]
    assert early.data["primary_measure"] == MEASURES[name.split("-", 1)[0]]
    assert early.data["elapsed_s"] >= 0
    assert early.recorded is False


STAGES = {
    "F1": (("r1_tenant",), False),
    "F2": (("continuity",), False),
    "F3": ((), False),  # scope counts come from the applied diff, on the host
    "F4": (("hidden_tests",), True),
    "F5": ((), False),  # no primary measure (F5-F7, controls)
}


@pytest.mark.parametrize("feature", sorted(STAGES))
def test_primary_stage_per_feature(feature: str) -> None:
    assert primary_stage(MEASURES[feature]) == STAGES[feature]


def test_primary_fields_include_the_totals_a_count_is_compared_with() -> None:
    assert primary_fields("hidden_passed,mutants_killed") == [
        "hidden_passed",
        "hidden_total",
        "mutants_killed",
        "mutants_total",
    ]
    assert primary_fields("out_of_scope_files>=1 or test_phase_source_edits>=1") == [
        "out_of_scope_files",
        "test_phase_source_edits",
    ]
    assert primary_fields("continuity_failure") == ["continuity_failure"]
    assert primary_fields("") == []


def test_an_unknown_field_waits_for_every_check() -> None:
    assert primary_stage("velocity>=3") == (REFEREE_CHECKS, True)


@pytest.mark.parametrize("feature", sorted(STAGES))
def test_primary_checks_run_first_and_the_verdict_comes_before_the_rest(
    feature: str, course_repo: Path, tmp_path: Path
) -> None:
    _verdict, events, factory = run_scenario(f"{feature}-red", course_repo, tmp_path)
    checks, mutants_first = STAGES[feature]
    rest = tuple(c for c in REFEREE_CHECKS if c not in checks)
    arm_runs = [entry for entry in factory.order if entry[0] == "runner"][1:]  # after the baseline
    assert arm_runs == ([("runner", checks)] if checks else []) + [("runner", rest)]
    mutant_at = [i for i, entry in enumerate(factory.order) if entry[0] == "mutant"]
    rest_at = factory.order.index(("runner", rest))
    assert all((i < rest_at) == mutants_first for i in mutant_at)
    [early] = [e for e in events if e.type == "primary_verdict"]
    secondary = [e.seq for e in events if e.type == "check_result" and e.data["check"] in rest]
    primary = [e.seq for e in events if e.type == "check_result" and e.data["check"] in checks]
    assert all(seq < early.seq for seq in primary)
    assert secondary and all(seq > early.seq for seq in secondary)
    killed = [e.seq for e in events if e.type == "mutant_result"]
    assert all((seq < early.seq) == mutants_first for seq in killed)


def test_check_inputs_are_written_once_for_both_stages(course_repo: Path, tmp_path: Path) -> None:
    _verdict, _events, factory = run_scenario("F1-green", course_repo, tmp_path)
    assert factory.arm_box is not None
    writes = [c for c in factory.arm_box.commands if c.startswith("printf") and "params" in c]
    assert len(writes) == 1


@pytest.mark.parametrize("name", LATE_FAILURES)
def test_a_failure_after_the_primary_verdict_still_fails_the_record_as_before(
    name: str, expected: dict[str, Any], course_repo: Path, tmp_path: Path
) -> None:
    verdict, events, _f = run_scenario(name, course_repo, tmp_path)
    assert outcome(verdict) == expected[name]
    assert verdict.record.passed_primary is False
    assert [e.type for e in events].count("primary_verdict") == 1
    assert events[-1].type == "verdict" and events[-1].data["passed_primary"] is False
    assert "could not judge" in events[-1].data["summary"]


def test_elapsed_time_counts_from_the_end_of_the_arm(course_repo: Path, tmp_path: Path) -> None:
    ended = time.monotonic() - 5.0
    _verdict, events, _f = run_scenario("F2-green", course_repo, tmp_path, arm_ended=ended)
    [early] = [e for e in events if e.type == "primary_verdict"]
    assert 5.0 <= early.data["elapsed_s"] < 60.0


def test_a_replayed_judgement_marks_its_primary_verdict_recorded(
    course_repo: Path, tmp_path: Path
) -> None:
    _verdict, events, _f = run_scenario("F4-green", course_repo, tmp_path, recorded=True)
    [early] = [e for e in events if e.type == "primary_verdict"]
    assert early.recorded is True and early.data["passed"] is True
    assert early.data["values"] == {"hidden_passed": 4, "mutants_killed": 2}
