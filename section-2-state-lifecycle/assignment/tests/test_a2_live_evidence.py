"""The required live step: the four-session task, the evidence files, and their checks.

All evidence here is a SYNTHETIC TEST FIXTURE (tests/a2_live_fixture.py); no model is called.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import a2_live_fixture as fx  # noqa: E402
from a2_scenario import live_evidence as le  # noqa: E402

STARTER = ASSIGNMENT / "starter"


@pytest.fixture
def impl(tmp_path: Path) -> Path:
    """A learner folder: a copy of the starter's a2_state package."""
    folder = tmp_path / "my-a2"
    shutil.copytree(STARTER / "a2_state", folder / "a2_state")
    return folder


def _evidence(impl: Path, tmp_path: Path, **options: object) -> Path:
    return fx.write_evidence(impl, tmp_path / "work", **options)


def _rewrite_json(path: Path, change) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


# -- the task -----------------------------------------------------------------------------------


def test_the_live_task_is_an_f2_task_with_four_sessions() -> None:
    source = le.load_example(le.FEATURES_FILE, le.SOURCE_EXAMPLE)
    line = le.derive_task_line(source)
    assert line["inputs"]["feature_id"] == "F2"
    assert line["inputs"]["checkpoint"] == source["inputs"]["checkpoint"]
    assert line["inputs"]["session_budget"] == [10, 10, 10, 20]
    assert len(line["inputs"]["session_budget"]) == le.FORCED_STOPS + 1 == 4
    # the same build turns as every F2 line of the dataset, split over four sessions
    assert sum(line["inputs"]["session_budget"]) == sum(source["inputs"]["session_budget"])
    assert line["inputs"]["variant"] == le.LIVE_VARIANT
    assert line["metadata"]["example_id"] == le.LIVE_EXAMPLE_ID
    assert "runs over four sessions" in line["inputs"]["ticket_text"]
    assert "two sessions" not in line["inputs"]["ticket_text"]
    assert line["outputs"] == source["outputs"]  # same hidden tests, mutants, primary measure


def test_the_inner_command_is_an_ab_on_the_live_task() -> None:
    command = le.inner_command("my-a2/live/task.jsonl")
    assert command[0] == "ab"
    assert command[command.index("--dataset") + 1] == "my-a2/live/task.jsonl"
    assert command[command.index("--example") + 1] == le.LIVE_EXAMPLE_ID
    assert command[command.index("--layers") + 1] == "instructions,state"
    assert "--no-reviewer" in command
    # The LangSmith project for assignments: without it `ab` defaults to the class purpose, which
    # needs SHIPHARNESS_CLASS_DATE and traces into the class project.
    assert command[command.index("--purpose") + 1] == "assignment"


def test_the_caps_and_model_come_from_the_course_settings() -> None:
    assert le.LIVE_MODEL == "gpt-6-luna"
    assert le.RUN_CAP_USD == 0.20
    assert le.COMMAND_CAP_USD == 2.50


# -- the summary and the checks -----------------------------------------------------------------


def test_the_summary_records_sessions_and_stops_per_arm(tmp_path: Path) -> None:
    ab_dir = fx.write_run(tmp_path / "runs", tmp_path / "exports")
    summary = le.build_summary(ab_dir, layer=fx.LAYER_NAME, digest="d", impl="my-a2")
    harness = summary["arms"]["harness"]
    assert summary["ab_id"] == fx.AB_ID
    assert harness["run_id"] == fx.RUN_IDS["harness"]
    assert harness["model"] == le.LIVE_MODEL
    assert [s["session_index"] for s in harness["session_stops"]] == [1, 2, 3]
    assert [s["ended_by"] for s in harness["sessions"] if s["phase"] == "build"] == [
        "turn_budget",
        "turn_budget",
        "turn_budget",
        "claim_done",
    ]
    assert summary["layer"] == {"class": fx.LAYER_NAME, "impl": "my-a2", "a2_state_sha256": "d"}


def test_synthetic_evidence_is_valid(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path)
    assert le.validate(impl) == []
    names = {p.name for p in evidence.iterdir()}
    assert {"task.jsonl", "summary.json", "output.txt", "command.txt", "scores"} <= names
    assert {p.name for p in (evidence / "scores").iterdir()} == {
        f"{run_id}.json" for run_id in fx.RUN_IDS.values()
    }


def test_missing_evidence_is_named(impl: Path) -> None:
    problems = le.validate(impl)
    assert len(problems) == 1 and "live/ not found" in problems[0]


def test_fewer_forced_stops_fail(impl: Path, tmp_path: Path) -> None:
    _evidence(impl, tmp_path, stops=1)
    problems = "\n".join(le.validate(impl))
    assert "4 build sessions" in problems
    assert "3 session_stop events" in problems


AGENT_ENDED = ["turn_budget", "claim_not_done", "turn_budget"]


def test_the_summary_records_what_each_stop_step_left(tmp_path: Path) -> None:
    ab_dir = fx.write_run(tmp_path / "runs", tmp_path / "exports", harness_ends=AGENT_ENDED)
    summary = le.build_summary(ab_dir, layer=fx.LAYER_NAME, digest="d", impl="my-a2")
    stop = summary["arms"]["harness"]["session_stops"][1]
    assert stop["session_index"] == 2
    assert stop["ended_by"] == "claim_not_done"
    assert stop["handoff_path"] == "session-handoff.md"
    assert {"session-handoff.md", "progress.md"} <= set(stop["state_paths"])
    assert stop["end_sha"] != stop["resume_sha"]


def test_an_agent_ended_session_counts_as_a_stop_when_the_stop_step_ran(
    impl: Path, tmp_path: Path
) -> None:
    # Owner decision (2026-10-18): finish(claim="not_done") ends a session like the turn budget
    # when the harness stop step wrote and committed the handoff and progress for that session.
    _evidence(impl, tmp_path, harness_ends=AGENT_ENDED)
    assert le.validate(impl) == []


def test_an_agent_ended_session_without_the_stop_step_fails(impl: Path, tmp_path: Path) -> None:
    _evidence(impl, tmp_path, harness_ends=AGENT_ENDED, stop_step=False)
    problems = "\n".join(le.validate(impl))
    assert "session 2 ended by claim_not_done" in problems
    assert "4 build sessions" in problems


def test_an_agent_ended_session_from_an_older_summary_fails(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path, harness_ends=AGENT_ENDED)

    def strip(data: dict) -> None:  # type: ignore[type-arg]
        for stop in data["arms"]["harness"]["session_stops"]:
            for key in ("handoff_path", "state_paths", "end_sha", "resume_sha"):
                stop.pop(key, None)

    _rewrite_json(evidence / "summary.json", strip)
    assert any("claim_not_done" in p for p in le.validate(impl))


@pytest.mark.parametrize("end", ["timeout", "claim_done", "error"])
def test_any_other_session_end_still_fails(impl: Path, tmp_path: Path, end: str) -> None:
    _evidence(impl, tmp_path, harness_ends=["turn_budget", end, "turn_budget"])
    assert any("4 build sessions" in p for p in le.validate(impl))


def test_another_model_fails(impl: Path, tmp_path: Path) -> None:
    _evidence(impl, tmp_path, model="gpt-5.6-luna")
    assert any("model gpt-5.6-luna" in p for p in le.validate(impl))


def test_a_recorded_or_unsandboxed_run_fails(impl: Path, tmp_path: Path) -> None:
    records = {
        "bare": fx.score_record("bare", recorded=True),
        "harness": fx.score_record("harness", sandboxed=False),
    }
    _evidence(impl, tmp_path, records=records)
    problems = "\n".join(le.validate(impl))
    assert "recorded" in problems and "sandboxed" in problems


def test_a_run_over_the_cap_fails(impl: Path, tmp_path: Path) -> None:
    records = {arm: fx.score_record(arm) for arm in fx.RUN_IDS}
    records["harness"] = fx.score_record("harness", cost_usd=0.25)
    _evidence(impl, tmp_path, records=records)
    assert any("over the run cap" in p for p in le.validate(impl))


def test_a_cost_line_over_the_command_cap_fails(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path)
    text = (evidence / "output.txt").read_text(encoding="utf-8")
    text = text.replace("Cost: $0.020000", "Cost: $2.600000")
    (evidence / "output.txt").write_text(text, encoding="utf-8")
    assert any("over the per-command cap" in p for p in le.validate(impl))


def test_a_missing_cost_line_fails(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path)
    text = (evidence / "output.txt").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("Cost: ")]
    (evidence / "output.txt").write_text("\n".join(lines), encoding="utf-8")
    assert any("no `Cost: $...` line" in p for p in le.validate(impl))


def test_a_layer_changed_after_the_run_fails(impl: Path, tmp_path: Path) -> None:
    _evidence(impl, tmp_path)
    layer = impl / "a2_state" / "layer.py"
    layer.write_text(layer.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert any("a2_state" in p and "differs" in p for p in le.validate(impl))


def test_run_ids_must_agree(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path)
    _rewrite_json(
        evidence / "summary.json",
        lambda d: d["arms"]["harness"].update(run_id="run-synthetic-fixture-other"),
    )
    assert any("run id" in p for p in le.validate(impl))


def test_a_malformed_score_record_fails(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path)
    path = evidence / "scores" / f"{fx.RUN_IDS['harness']}.json"
    _rewrite_json(path, lambda d: d.pop("checkpoint_sha"))
    _rewrite_json(path, lambda d: d.update(extra_field=1))
    assert any("not a ScoreRecord" in p for p in le.validate(impl))


def test_the_command_must_be_the_live_task(impl: Path, tmp_path: Path) -> None:
    evidence = _evidence(impl, tmp_path)
    (evidence / "command.txt").write_text("shipharness ab --example F2-canonical\n", "utf-8")
    assert any("command.txt" in p for p in le.validate(impl))


# -- finding the submission ---------------------------------------------------------------------


def test_find_submission_accepts_the_folder_or_a_repo_holding_it(
    impl: Path, tmp_path: Path
) -> None:
    _evidence(impl, tmp_path)
    assert le.find_submission(impl) == impl
    repo = tmp_path / "repo"
    shutil.copytree(STARTER, repo / "submodules" / "a2" / "starter")  # a second a2_state, no live/
    shutil.copytree(impl, repo / "work" / "my-a2")
    assert le.find_submission(repo) == repo / "work" / "my-a2"


def test_find_submission_refuses_an_ambiguous_repo(impl: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(impl, repo / "one")
    shutil.copytree(impl, repo / "two")
    with pytest.raises(FileNotFoundError, match="2 folders"):
        le.find_submission(repo)
