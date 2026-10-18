"""Scenario runs through the real runner loop, and the measures the self-check and grader use."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))

from a2_scenario.live_evidence import LIVE_KEY, LIVE_POINTS  # noqa: E402
from a2_scenario.measures import CRITERIA, evaluate, scenario_points, total_points  # noqa: E402
from a2_scenario.runner import run_scenario  # noqa: E402
from a2_scenario.scenarios import VISIBLE  # noqa: E402

from shipharness.harness.base import BaseLayer, LayerContext  # noqa: E402
from shipharness.harness.state.handoff import migration_heads  # noqa: E402
from shipharness.runner.models import SessionResult  # noqa: E402

V1 = VISIBLE[0]


class NoStateLayer(BaseLayer):
    """Keeps nothing between sessions: what a layer without TODOs 1-7 does."""

    name = "state"

    def __init__(self, **_kwargs: object) -> None:
        pass


class TellingLayer(BaseLayer):
    """A test-only layer that tells the next session which steps git shows as committed, and the
    migration head. It writes no progress file, exec plan, or handoff."""

    name = "state"

    def __init__(self, **_kwargs: object) -> None:
        self.lines: list[str] = []

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list:
        log = ctx.sandbox.exec("git log --format=%s", 30).output
        done = sorted({s.split(":")[0] for s in log.splitlines() if s[:1] == "S" and ":" in s})
        self.lines = [f"- [x] {step}" for step in done]
        self.lines.append(f"- Migration heads: {migration_heads(ctx.workspace)}")
        return []

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        return ["\n".join(self.lines)]


def outcomes(run) -> dict[str, float]:
    return {o.key: o.fraction for o in evaluate(run)}


def test_the_grading_criteria_add_up_to_100() -> None:
    """Scenario criteria plus the live-run evidence criterion (checked by the grader only)."""
    assert scenario_points() == 90 and LIVE_POINTS == 10
    assert total_points() == 100
    assert len({c.key for c in CRITERIA}) == len(CRITERIA)
    assert LIVE_KEY not in {c.key for c in CRITERIA}


@pytest.fixture(scope="module")
def no_state_run(tmp_path_factory: pytest.TempPathFactory):
    return run_scenario(lambda **kw: NoStateLayer(**kw), V1, tmp_path_factory.mktemp("none"))


def test_three_forced_stops_happen_and_unknown_work_is_redone(no_state_run) -> None:
    run = no_state_run
    assert run.result.status == "completed", run.result.error
    assert [s.ended_by for s in run.result.sessions] == ["turn_budget"] * 4
    session_2 = [a.label for a in run.agent.actions if a.session == 2]
    assert "write S1 migrations/versions/c1a2_comments.py" in session_2
    assert set(run.stop_trees) == {1, 2, 3, 4} and run.start_tree


def test_without_state_the_measures_fail(no_state_run) -> None:
    got = outcomes(no_state_run)
    for key in (
        "finished",
        "one_head",
        "fresh_upgrade",
        "no_duplicate_table",
        "no_redone_lines",
        "steps_once",
        "session_log",
        "plan_completed",
        "handoff",
    ):
        assert got[key] == 0.0, key


def test_a_layer_that_reports_git_evidence_lets_the_feature_finish(tmp_path: Path) -> None:
    run = run_scenario(lambda **kw: TellingLayer(**kw), V1, tmp_path)
    assert [s.ended_by for s in run.result.sessions][-1] == "claim_done"
    got = outcomes(run)
    for key in (
        "finished",
        "one_head",
        "fresh_upgrade",
        "no_duplicate_table",
        "no_redone_lines",
        "steps_once",
        "clean_tree",
    ):
        assert got[key] == 1.0, (key, [o for o in evaluate(run) if o.key == key])
    for key in ("session_log", "plan_completed", "plan_ledger", "plan_sessions", "handoff"):
        assert got[key] == 0.0, key


def test_a_layer_error_is_recorded_with_its_traceback(tmp_path: Path) -> None:
    class Broken(NoStateLayer):
        def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list:
            raise RuntimeError("boom in on_session_end")

    run = run_scenario(lambda **kw: Broken(**kw), V1, tmp_path)
    assert run.result.status == "ERROR"
    assert any("boom in on_session_end" in e for e in run.errors)


def test_criteria_name_the_progress_sections_and_cite_no_private_file() -> None:
    """Learners see the titles: the six progress.md sections are spelled out, nothing points at a
    file outside the learner repository."""
    titles = {c.key: c.title for c in CRITERIA}
    for section in ("# Progress", "Current feature", "Done", "In progress", "Next", "Session log"):
        assert section in titles["progress_sections"], section
    for c in CRITERIA:  # no section-number citations such as "(<file> 15.2)" or "§5"
        assert not re.search(r"\d+\.\d+|§", c.title + c.hint), c.key
