"""ConsoleState folds events into the view model behind the five screens."""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.console.state import ConsoleState
from shipharness.events import EVENT_DATA_MODELS, read_events
from tests.unit.console.fixture_log import LEAK_DETAIL, build_fixture_run


@pytest.fixture(scope="module")
def log(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_fixture_run(tmp_path_factory.mktemp("runs"))


@pytest.fixture(scope="module")
def state(log: Path) -> ConsoleState:
    return ConsoleState.from_events(read_events(log))


def test_fixture_covers_every_event_type(log: Path) -> None:
    assert {e.type for e in read_events(log)} == set(EVENT_DATA_MODELS)


def test_sandbox_header_usage_and_cost(state: ConsoleState) -> None:
    bare = state.arm("bare")
    assert bare.sandbox is not None and bare.sandbox["container_id"] == "a1b2c3d4e5f6"
    assert bare.sandbox["network"] == "none"
    assert bare.usage is not None and bare.usage["time_left_s"] == 183
    assert bare.cost is not None and bare.cost["run_usd"] == pytest.approx(0.081)
    assert state.unsandboxed is False


def test_recent_turns_are_the_last_eight_with_session_markers(state: ConsoleState) -> None:
    rows = state.arm("harness").recent(8)
    assert len(rows) == 8
    kinds = [row.kind for row in rows]
    assert "session_stop" in kinds and "session_resume" in kinds
    last = rows[-1]
    assert last.kind == "turn" and (last.session_index, last.turn) == (2, 3)
    assert [t.name for t in last.tools] == ["apply_patch"]


def test_tool_results_attach_to_their_calls(state: ConsoleState) -> None:
    turn3 = next(r for r in state.arm("bare").timeline if r.kind == "turn" and r.turn == 3)
    [tool] = turn3.tools
    assert (tool.name, tool.target, tool.ok, tool.exit_code) == (
        "run",
        "pip install requests",
        False,
        126,
    )


def test_files_read_are_categorised(state: ConsoleState) -> None:
    harness = {f.path: f.category for f in state.arm("harness").files_read.values()}
    assert harness["AGENTS.md"] == "map"
    assert harness[".agents/skills/add-endpoint/SKILL.md"] == "skill"
    assert harness["docs/SECURITY.md"] == "harness doc"
    assert harness["progress.md"] == "state"
    assert {f.category for f in state.arm("bare").files_read.values()} == {"handbook"}


def test_skill_loads_are_marked_in_the_turn_list(state: ConsoleState) -> None:
    turn1 = next(r for r in state.arm("harness").timeline if r.kind == "turn")
    assert any(t.harness_doc for t in turn1.tools)
    assert any("skill loaded" in note for note in turn1.notes)


def test_gate_history_and_latest_gate(state: ConsoleState) -> None:
    harness = state.arm("harness")
    assert [g["gate_id"] for g in harness.gates] == ["g1", "g2"]
    assert harness.gate is not None and harness.gate["passed"] is True
    assert state.arm("bare").gate is None


def test_decisions_include_blocked_and_gate_outcomes(state: ConsoleState) -> None:
    kinds = [d.kind for d in state.arm("harness").decisions]
    assert "block" in kinds and "gate_fail" in kinds and "gate_pass" in kinds
    assert "blocked" in kinds  # the blocked event itself


def test_agent_claim_versus_referee(state: ConsoleState) -> None:
    bare, harness = state.arm("bare"), state.arm("harness")
    assert bare.claims["build"]["claim"] == "done"
    assert bare.verdict is not None and bare.verdict["passed_primary"] is False
    assert bare.claim_supported is False
    assert harness.claim_supported is True


def test_denials_and_diff_map(state: ConsoleState) -> None:
    bare, harness = state.arm("bare"), state.arm("harness")
    assert [d["reason_code"] for d in bare.denials] == ["network"]
    assert bare.diff_map() == {
        "app/api/issues.py": "changed",
        "app/repositories/issues.py": "changed",
        "app/seed.py": "out of scope",
    }
    assert harness.diff_map()["migrations/versions/0001_initial.py"] == "blocked"
    assert harness.diff_map()["app/repositories/issues.py"] == "changed"


def test_session_timeline_marks_redone_work(state: ConsoleState) -> None:
    sessions = state.arm("harness").sessions()
    assert [s.index for s in sessions] == [1, 2]
    assert sessions[0].ended_by == "session_turn_limit"
    assert sessions[1].redone == ["app/repositories/issues.py"]
    assert sessions[0].redone == []


def test_filter_table_mutants_and_checks(state: ConsoleState) -> None:
    harness, bare = state.arm("harness"), state.arm("bare")
    tests = harness.tests
    assert list(tests) == [
        "tests/test_labels.py::test_label_scoped_to_org",
        "tests/test_labels.py::test_label_with_mocks",
    ]
    mocked = tests["tests/test_labels.py::test_label_with_mocks"]
    assert mocked.kept is False and mocked.discard_reason == (
        "Filter 4: Real assertions (mocks the unit under test)"
    )
    assert tests["tests/test_labels.py::test_label_scoped_to_org"].kept is True
    assert [(m["mutant_id"], m["outcome"]) for m in harness.mutants if m["set"] == "filter"] == [
        ("m-issues-01", "killed"),
        ("m-issues-02", "survived"),
    ]
    assert bare.checks["r1_tenant"]["new_violations"] == 3
    assert bare.progress["R1"]["label"] == "House rule 1 probes 112/112"


def test_screenshots_and_trace_links(state: ConsoleState) -> None:
    bare = state.arm("bare")
    assert bare.screenshots["board"]["path"] == "screenshots/bare/board-0001.png"
    assert bare.screenshots["conflict"]["overlays"] == [{"issue_id": 1, "mark": "lost_update"}]
    assert bare.traces["agent"].endswith("bare-agent")
    assert state.ab.traces["comparison"].endswith("compare/ab-fixture")


def test_first_wrong_turn(state: ConsoleState) -> None:
    bare = state.arm("bare").first_wrong_turn()
    assert bare is not None
    assert (bare.session_index, bare.turn) == (1, 2)
    assert "app/repositories/issues.py" in bare.reason
    assert "House rule 1: Tenant isolation" in bare.reason
    harness = state.arm("harness").first_wrong_turn()
    assert harness is not None and (harness.session_index, harness.turn) == (1, 3)
    assert "blocked" in harness.reason
    assert LEAK_DETAIL  # the bare reason comes from this referee finding


def test_tail_is_newest_first_and_bounded(state: ConsoleState, log: Path) -> None:
    tail = state.tail(10)
    assert len(tail) == 10
    seqs = [line.seq for line in tail]
    assert seqs == sorted(seqs, reverse=True)
    assert tail[0].seq == max(e.seq for e in read_events(log))
    assert all(line.summary for line in tail)


def test_recorded_and_unsandboxed_flags(tmp_path: Path) -> None:
    log = build_fixture_run(tmp_path, recorded=True)
    state = ConsoleState.from_events(read_events(log))
    assert state.recorded is True
    assert ConsoleState().recorded is False


def test_unknown_arm_is_ignored_safely() -> None:
    state = ConsoleState()
    assert state.arm("bare").timeline == []
    assert state.arm("bare").first_wrong_turn() is None
