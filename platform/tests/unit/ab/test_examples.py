"""Constructed examples: `shipharness example --section demo-N` runs the
harness arm with section N's layer stack on its canonical task, driven by scripted steps that make
the mistake the layer exists to catch. These tests run each scenario with the real layers and a fake
sandbox, and check that a constructed run is never counted where a real run is counted."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from shipharness.ab import commands
from shipharness.ab.commands import FEATURES_FILE
from shipharness.ab.demo import ABTask, run_ab
from shipharness.ab.recorded import RecordedDeps, SingleArmRecord, latest_ab_dir, replay_ab
from shipharness.ab.recorded import swap_test as run_swap
from shipharness.ab.report import build_report
from shipharness.console.report import load_report
from shipharness.console.screens import ScreenContext, ScreenRenderer
from shipharness.console.state import ConsoleState
from shipharness.events import Event, read_events
from shipharness.examples import CONSTRUCTED_BADGE, SCENARIOS
from shipharness.examples import demo4_verify as demo4
from shipharness.examples.run import example_task, run_example, scripted_client_factory
from shipharness.sandbox import ExecResult, FakeSandbox, SandboxPolicy
from shipharness.sandbox._events import emit_denial
from shipharness.sandbox.policy import check_command
from shipharness.tracing import read_exports, write_export

from ..verify.fakes import ALL_GATE_CHECKS, check_result, runner_output
from .score_fixtures import record
from .test_commands import make_app
from .test_demo import Clients, make_deps
from .test_referee import Factory, all_green

LEAK = {
    "rule": "R1",
    "severity": "leak",
    "endpoint": "GET /issues",
    "detail": "no_path: GET /issues -> 200 (items of org globex)",
    "baseline": False,
}


class ArmSandbox(FakeSandbox):
    """A fake arm sandbox that refuses what the real sandbox policy refuses (and reports it on the
    bus, as DockerSandbox does) and answers the commands the layers run. The visible tests fail
    until `tests_pass_after` patches have been applied. With a `workspace`, every applied patch
    changes a file there, as a real `git apply` does (the harness reuses a visible-suite run only
    while the workspace content is unchanged)."""

    def __init__(
        self,
        bus: Any,
        run_id: str,
        arm: str,
        tests_pass_after: int = 0,
        workspace: Path | None = None,
    ) -> None:
        super().__init__(self._answer)
        self.bus, self.run_id, self.arm = bus, run_id, arm
        self.policy = SandboxPolicy()
        self.tests_pass_after = tests_pass_after
        self.applied = 0
        self.workspace = workspace

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        denial = check_command(self.policy, command)
        if denial is not None:
            self.commands.append(command)
            emit_denial(self.bus, self.run_id, self.arm, denial, command)  # type: ignore[arg-type]
            return ExecResult(
                exit_code=126, output=f"DENIED by sandbox: {denial.detail}", duration_ms=0,
                denied=denial,
            )  # fmt: skip
        return super().exec(command, timeout_s)

    def _answer(self, command: str) -> ExecResult:
        if command.startswith("git apply") and "--check" not in command:
            self.applied += 1
            if self.workspace is not None:
                marker = self.workspace / "tests" / "visible" / "applied_patches.txt"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(f"{self.applied}\n", encoding="utf-8")
        if "checks.runner" in command:
            results = [check_result(c) for c in ALL_GATE_CHECKS]
            return ExecResult(
                exit_code=0, output=runner_output(results, command=command), duration_ms=1
            )
        if "-m pytest" in command:
            if self.applied < self.tests_pass_after:
                output = (
                    f"FAILED {demo4.FAILING_TEST} - AssertionError\n1 failed, 30 passed in 1.0s\n"
                )
                return ExecResult(exit_code=1, output=output, duration_ms=1)
            return ExecResult(exit_code=0, output="31 passed in 1.0s\n", duration_ms=1)
        if command.startswith("alembic heads"):
            return ExecResult(exit_code=0, output="0001 (head)\n", duration_ms=1)
        return ExecResult(exit_code=0, output="", duration_ms=1)


def canonical(feature: str) -> ABTask:
    for line in FEATURES_FILE.read_text(encoding="utf-8").splitlines():
        data = json.loads(line)
        if data["inputs"]["feature_id"] == feature and data["inputs"]["variant"] == "canonical":
            # The miniature course repository has no mutant sets.
            return dataclasses.replace(ABTask.from_dataset_line(data), mutant_set="")
    raise AssertionError(feature)


def example(course_repo: Path, tmp_path: Path, section: str, **referee: Any):  # type: ignore[no-untyped-def]
    scenario = SCENARIOS[section]
    pass_after = 2 if section == "demo-4" else 0
    sandboxes: list[ArmSandbox] = []

    def sandbox_factory(arm, ws, bus, run_id):  # type: ignore[no-untyped-def]
        sandboxes.append(ArmSandbox(bus, run_id, arm, tests_pass_after=pass_after, workspace=ws))
        return sandboxes[-1]

    deps = make_deps(
        course_repo,
        tmp_path,
        Clients(),  # replaced by the scenario's scripted client
        sandbox_factory=sandbox_factory,
        referee_sandbox_factory=Factory(all_green(**referee)),
        layer_registry=None,  # the real layers
    )
    task = example_task(scenario, canonical(scenario.feature))
    result = run_example(scenario, task, deps)
    events = list(read_events(result.run_dir / "events.jsonl"))
    return result, events, sandboxes


def first(events: list[Event], predicate) -> Event:  # type: ignore[no-untyped-def]
    return next(e for e in events if predicate(e))


def decisions(events: list[Event], kind: str) -> list[Event]:
    return [e for e in events if e.type == "harness_decision" and e.data["kind"] == kind]


# -- the four scenarios ------------------------------------------------------------------------


def test_every_section_has_one_scenario_with_its_canonical_feature() -> None:
    assert {s: (v.section, v.feature) for s, v in SCENARIOS.items()} == {
        "demo-1": ("demo-1", "F1"),
        "demo-2": ("demo-2", "F2"),
        "demo-3": ("demo-3", "F3"),
        "demo-4": ("demo-4", "F4"),
    }
    for scenario in SCENARIOS.values():
        assert scenario.title and scenario.demonstrates
        assert all(
            step.usage.input_tokens == step.usage.output_tokens == 0 for step in scenario.steps()
        )


def test_scenarios_name_house_rules_in_full_never_as_bare_codes() -> None:
    for scenario in SCENARIOS.values():
        for text in (scenario.title, scenario.demonstrates):
            assert not re.search(r"\b[FRSA][1-8]\b", text), text
    assert "House rule 1: Tenant isolation" in SCENARIOS["demo-1"].demonstrates


def test_scenario_files_say_they_are_constructed_and_what_they_show() -> None:
    import importlib

    for name in ("demo1_instructions", "demo2_state", "demo3_scope", "demo4_verify"):
        module = importlib.import_module(f"shipharness.examples.{name}")
        doc = module.__doc__ or ""
        assert "constructed example" in doc.lower(), name
        assert "demonstrates" in doc.lower(), name


def test_demo_1_reads_the_map_and_one_document_then_leaks_and_r1_reports_it(
    course_repo: Path, tmp_path: Path
) -> None:
    result, events, _ = example(
        course_repo, tmp_path, "demo-1", r1_tenant=check_result("r1_tenant", findings=[LEAK], new=1)
    )
    reads = [
        e.data["target"] for e in events if e.type == "tool_call" and e.data["name"] == "read_file"
    ]
    assert reads[:2] == ["AGENTS.md", "docs/design-docs/api-conventions.md"]
    notes = [
        e.data["message"] for e in decisions(events, "note") if e.data["layer"] == "instructions"
    ]
    assert "agent read AGENTS.md" in notes
    [patch] = [e for e in events if e.type == "tool_call" and e.data["name"] == "apply_patch"]
    assert "app/repositories/issues.py" in patch.data["target"]
    claim = first(events, lambda e: e.type == "claim")
    assert (claim.data["phase"], claim.data["claim"]) == ("build", "done")
    r1 = first(events, lambda e: e.type == "check_result" and e.data["check"] == "r1_tenant")
    assert r1.data["new_violations"] == 1 and r1.data["findings"][0]["severity"] == "leak"
    assert claim.seq < r1.seq
    harness = result.arms["harness"]
    assert harness.record.r1_new_violations == 1 and harness.record.passed_primary is False
    assert harness.spec.layers == frozenset({"instructions"})


def test_demo_1_patch_is_a_query_without_the_org_filter() -> None:
    from shipharness.examples import demo1_instructions as demo1

    added = [line for line in demo1.LEAK_PATCH.splitlines() if line.startswith("+")]
    assert any("select(Issue).where(Issue.deleted_at.is_(None))" in line for line in added)
    assert not any("org_id" in line for line in added)
    assert '@router.get("/issues"' in demo1.LEAK_PATCH


def test_demo_2_stops_on_the_turn_budget_and_resumes_from_the_handoff(
    course_repo: Path, tmp_path: Path
) -> None:
    result, events, _ = example(course_repo, tmp_path, "demo-2")
    assert result.arms["harness"].spec.session_budget == [3, 4]
    stop = first(events, lambda e: e.type == "session_stop")
    resume = first(events, lambda e: e.type == "session_resume")
    assert stop.data["session_index"] == 1 and stop.data["ended_by"] == "turn_budget"
    assert stop.data["handoff_path"] == "session-handoff.md"
    assert resume.data["session_index"] == 2 and stop.seq < resume.seq
    [written] = [e for e in decisions(events, "session_stop") if e.seq < resume.seq]
    assert written.data["paths"] == ["session-handoff.md", "progress.md"]
    after = first(events, lambda e: e.type == "tool_call" and e.seq > resume.seq)
    assert (after.data["name"], after.data["target"]) == ("read_file", "session-handoff.md")
    claim = first(events, lambda e: e.type == "claim")
    assert claim.seq > resume.seq and claim.data["claim"] == "done"
    workspace = result.arms["harness"].spec.workspace
    assert "Machine summary" in (workspace / "session-handoff.md").read_text(encoding="utf-8")


def test_demo_3_is_blocked_outside_scope_denied_the_network_then_works_in_scope(
    course_repo: Path, tmp_path: Path
) -> None:
    result, events, sandboxes = example(course_repo, tmp_path, "demo-3")
    blocked = first(events, lambda e: e.type == "blocked")
    assert blocked.data["paths"] == ["app/api/middleware.py"]
    assert blocked.data["action"] == "reject_patch"
    denied = first(events, lambda e: e.type == "sandbox_denied")
    assert denied.data["reason_code"] == "network" and "pip install" in denied.data["command"]
    assert blocked.seq < denied.seq
    patches = [e for e in events if e.type == "tool_call" and e.data["name"] == "apply_patch"]
    assert len(patches) == 3  # middleware (blocked), the in-scope change, the test-phase tests
    assert "app/api/issues.py" in patches[1].data["target"]
    assert len([e for e in events if e.type == "blocked"]) == 1
    claim = first(events, lambda e: e.type == "claim")
    assert claim.seq > denied.seq and claim.data["claim"] == "done"
    # The blocked patch never reached the sandbox; the in-scope one did.
    applied = [c for c in sandboxes[0].commands if c.startswith("git apply") and "--check" not in c]
    assert len(applied) == 2
    assert result.arms["harness"].spec.layers == frozenset({"instructions", "state", "scope"})


def test_demo_4_gate_refuses_the_failing_test_then_passes_after_the_fix(
    course_repo: Path, tmp_path: Path
) -> None:
    result, events, _ = example(course_repo, tmp_path, "demo-4")
    fail = decisions(events, "gate_fail")
    passes = decisions(events, "gate_pass")
    assert len(fail) == 1 and len(passes) >= 1
    assert fail[0].seq < passes[0].seq
    assert demo4.FAILING_TEST in fail[0].data["message"]
    refused = first(
        events,
        lambda e: e.type == "tool_result" and e.data["output_excerpt"].startswith("Not accepted"),
    )
    assert demo4.FAILING_TEST in refused.data["output_excerpt"]
    claims = [e for e in events if e.type == "claim" and e.data["phase"] == "build"]
    assert [c.data["claim"] for c in claims] == ["done", "done"]
    assert claims[0].data["gate_id"] != claims[1].data["gate_id"]
    tests = [e for e in events if e.type == "claim" and e.data["phase"] == "test"]
    assert [c.data["claim"] for c in tests] == ["done"]
    assert result.arms["harness"].result.claim == "done"
    assert result.arms["harness"].spec.layers == frozenset(
        {"instructions", "state", "scope", "verify"}
    )


# -- marking and exclusion ---------------------------------------------------------------------


def test_a_constructed_run_costs_nothing_and_is_marked_everywhere(
    course_repo: Path, tmp_path: Path
) -> None:
    result, events, _ = example(course_repo, tmp_path, "demo-3")
    harness = result.arms["harness"]
    assert harness.result.cost_usd == 0.0
    assert {e.data["call_usd"] for e in events if e.type == "cost"} == {0.0}
    [start] = [e for e in events if e.type == "run_start"]
    assert start.data["spec"]["constructed"] is True and start.data["spec"]["single_arm"] is True
    data = json.loads((result.run_dir / "ab.json").read_text(encoding="utf-8"))
    assert (data["constructed"], data["single_arm"], data["mode"]) == (
        True,
        True,
        "constructed example",
    )
    assert harness.record.constructed is True and harness.record.single_arm is True
    kept = json.loads((result.run_dir / "harness" / "score.json").read_text(encoding="utf-8"))
    assert kept["constructed"] is True and kept["run_id"] == harness.spec.run_id


def test_a_constructed_run_writes_no_export(course_repo: Path, tmp_path: Path) -> None:
    example(course_repo, tmp_path, "demo-1")
    assert read_exports("scores", tmp_path / "exports") == []


def test_the_ab_report_and_screen_4_leave_constructed_records_out(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    rows = [("bare", False, False), ("harness", False, False), ("harness", True, True)]
    for i, (arm, single, constructed) in enumerate(rows):
        rec = record(
            run_id=f"r-{i}", arm=arm, primary={"r1_new_violations": 0}, single_arm=single,
            constructed=constructed,
        )  # fmt: skip
        write_export("scores", rec.run_id, rec, exports)
    report = build_report(exports, include_recorded=True)
    assert report["runs"] == 2
    screen = load_report(exports)
    assert [(g.arm, len(g.dots)) for g in screen.groups] == [("bare", 1), ("harness", 1)]
    assert screen.constructed == 1 and screen.single_arm == 0
    # Even without the single-arm mark, a constructed record is never a dot.
    lone = record(run_id="r-9", arm="harness", constructed=True)
    write_export("scores", lone.run_id, lone, exports)
    assert load_report(exports).constructed == 2
    assert build_report(exports)["runs"] == 2


def test_swap_skips_and_refuses_a_constructed_run(course_repo: Path, tmp_path: Path) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    task = ABTask.from_dataset_line(
        {
            "inputs": {"feature_id": "F1", "checkpoint": "m1-s1-start", "ticket_text": "t"},
            "outputs": {"primary_measure": "r1_new_violations>=1"},
        }
    )
    both = run_ab(task, frozenset({"instructions"}), deps, section="demo-1")
    result, _, _ = example(course_repo, tmp_path, "demo-1")
    assert latest_ab_dir(tmp_path / "runs", "demo-1") == both.run_dir
    recorded = RecordedDeps(
        course_repo=course_repo,
        referee_sandbox_factory=Factory(all_green()),
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    with pytest.raises(SingleArmRecord, match="constructed example"):
        run_swap(result.run_dir, recorded)


def test_a_replay_of_a_constructed_run_stays_constructed_and_unexported(
    course_repo: Path, tmp_path: Path
) -> None:
    result, _, _ = example(course_repo, tmp_path, "demo-1")
    recorded = RecordedDeps(
        course_repo=course_repo,
        referee_sandbox_factory=Factory(all_green()),
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    out = replay_ab(result.run_dir, recorded)
    assert out.records["harness"].constructed is True
    assert read_exports("scores", tmp_path / "exports") == []
    assert (out.run_dir / "harness" / "score.json").is_file()


def test_run_ab_refuses_a_constructed_ab_with_both_arms(course_repo: Path, tmp_path: Path) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    with pytest.raises(ValueError, match="constructed"):
        run_ab(canonical("F1"), frozenset({"instructions"}), deps, constructed=True)


def test_a_script_that_runs_out_still_costs_nothing() -> None:
    from shipharness.examples.base import Scenario

    empty = Scenario(section="demo-1", feature="F1", title="t", demonstrates="d", steps=list)
    client = scripted_client_factory(empty)("harness")
    for _ in range(3):
        response = client.respond(
            [], [], model="m", effort="low", max_output_tokens=1, service_tier="auto"
        )
        assert (response.usage.input_tokens, response.usage.output_tokens) == (0, 0)
        assert not [i for i in response.output_items if i.get("type") == "function_call"]


def test_the_scripted_client_serves_the_harness_arm_only() -> None:
    factory = scripted_client_factory(SCENARIOS["demo-1"])
    assert factory("harness").steps  # a fresh script for each client
    with pytest.raises(ValueError, match="harness arm"):
        factory("bare")


# -- console -----------------------------------------------------------------------------------


def screens_of(run_dir: Path, exports: Path) -> dict[str, str]:
    state = ConsoleState.from_events(read_events(run_dir / "events.jsonl"))
    ctx = ScreenContext(run_dir.name, state, load_report(exports), str(exports))
    return ScreenRenderer().render_all(ctx)


def test_every_console_screen_shows_the_constructed_badge(
    course_repo: Path, tmp_path: Path
) -> None:
    result, _, _ = example(course_repo, tmp_path, "demo-2")
    state = ConsoleState.from_events(read_events(result.run_dir / "events.jsonl"))
    assert state.constructed is True
    screens = screens_of(result.run_dir, tmp_path / "exports")
    assert set(screens) == {"1", "2", "3", "4", "5"}
    for key, html in screens.items():
        assert CONSTRUCTED_BADGE in html, key
        assert "HARNESS IN ACTION" not in html, key  # a constructed example is not a live run


def test_a_real_run_shows_no_constructed_badge(course_repo: Path, tmp_path: Path) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    task = canonical("F1")
    result = run_ab(task, frozenset({"instructions"}), deps, arms=("harness",))
    assert (
        ConsoleState.from_events(read_events(result.run_dir / "events.jsonl")).constructed is False
    )
    for html in screens_of(result.run_dir, tmp_path / "exports").values():
        assert CONSTRUCTED_BADGE not in html


def test_screen_4_counts_constructed_records_it_leaves_out(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    rec = record(run_id="r-1", arm="harness", single_arm=True, constructed=True)
    write_export("scores", rec.run_id, rec, exports)
    log = tmp_path / "runs" / "ab-1" / "events.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("", encoding="utf-8")
    assert "1 constructed example" in screens_of(log.parent, exports)["4"]


# -- command ---------------------------------------------------------------------------------


@pytest.fixture
def example_env(course_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    from shipharness.config import Settings

    settings = Settings(
        _env_file=None, runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports"
    )

    def sandbox_factory(arm, ws, bus, run_id):  # type: ignore[no-untyped-def]
        return ArmSandbox(bus, run_id, arm)

    deps = make_deps(
        course_repo,
        tmp_path,
        Clients(),
        sandbox_factory=sandbox_factory,
        layer_registry=None,
        mutants=[],
    )
    seen: dict[str, Any] = {}

    def runtime(settings_, project, **kw):  # type: ignore[no-untyped-def]
        seen.update(project=project, tracing=settings_.langsmith_tracing, **kw)
        return SimpleNamespace(ab_deps=lambda ref, reviewer=True, **k: seen.update(
            ref=ref, reviewer=reviewer, **k) or deps)  # fmt: skip

    def no_live_guard(*a: Any, **k: Any) -> None:
        raise AssertionError("a constructed example never goes through the live-client guard")

    monkeypatch.setattr(commands, "_settings", lambda: settings)
    monkeypatch.setattr(commands, "_runtime", runtime)
    monkeypatch.setattr(commands, "_live_guard", no_live_guard)
    dataset = tmp_path / "features.jsonl"
    lines = [
        json.dumps({**line, "outputs": {**line["outputs"], "mutant_set": ""}})
        for line in map(json.loads, FEATURES_FILE.read_text(encoding="utf-8").splitlines())
    ]
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return SimpleNamespace(dataset=dataset, seen=seen, tmp=tmp_path)


def test_example_command_runs_the_scenario_at_no_cost(example_env) -> None:  # type: ignore[no-untyped-def]
    args = ["example", "--section", "demo-3", "--no-preview", "--dataset", str(example_env.dataset)]
    result = CliRunner().invoke(make_app(), args)
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert lines[0].startswith(CONSTRUCTED_BADGE)
    assert "(Section 3: Scope and sandbox, demo-3: " in lines[0]
    assert any("(Feature 3: Safe retries for issue creation, layers=" in line for line in lines)
    assert any(line.startswith("A/B ") and "constructed example" in line for line in lines)
    assert any("BLOCKED" in line and "app/api/middleware.py" in line for line in lines)
    assert any("DENIED network" in line for line in lines)
    assert lines[-1].startswith("Cost: $0.000000 (constructed example")
    assert example_env.seen["tracing"] is False  # no LangSmith
    assert example_env.seen["reviewer"] is False  # no OpenAI reviewer
    assert example_env.seen["preview_factory"] is None
    assert read_exports("scores", example_env.tmp / "exports") == []


def test_example_command_refuses_an_unknown_section(example_env) -> None:  # type: ignore[no-untyped-def]
    result = CliRunner().invoke(make_app(), ["example", "--section", "final"])
    assert result.exit_code == 2
    assert "demo-1" in result.output and "demo-4" in result.output
    assert "Traceback" not in result.output
