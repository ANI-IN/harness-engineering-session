"""`shipharness ab --arms harness`: the harness arm alone, judged by the same
referee with the same events ("harness in action", `make show-N`). Its records are marked single-arm
and are left out of every bare-vs-harness comparison; swap tests skip them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shipharness.ab.demo import ABTask, run_ab
from shipharness.ab.recorded import RecordedDeps, SingleArmRecord, latest_ab_dir, replay_ab
from shipharness.ab.recorded import swap_test as run_swap
from shipharness.ab.report import build_report
from shipharness.console.report import load_report
from shipharness.events import read_events
from shipharness.tracing import read_exports, write_export

from .score_fixtures import record
from .test_commands import _one_line_error, env, make_app  # noqa: F401 - env is a fixture
from .test_demo import LINE, Clients, make_deps
from .test_referee import Factory, all_green


def harness_only(course_repo: Path, tmp_path: Path, **kw):  # type: ignore[no-untyped-def]
    clients = Clients()
    deps = make_deps(course_repo, tmp_path, clients, **kw)
    task = ABTask.from_dataset_line(LINE)
    result = run_ab(task, frozenset({"instructions"}), deps, section="demo-1", arms=("harness",))
    return result, clients, deps


def test_only_the_harness_arm_runs_and_is_judged(course_repo: Path, tmp_path: Path) -> None:
    result, clients, _deps = harness_only(course_repo, tmp_path)
    assert set(result.arms) == {"harness"}
    assert set(clients.clients) == {"harness"}  # no model client for the bare arm
    events = list(read_events(result.run_dir / "events.jsonl"))
    assert {e.arm for e in events if e.type == "run_start"} == {"harness"}
    assert {e.arm for e in events if e.type == "verdict"} == {"harness"}
    [start] = [e for e in events if e.type == "run_start"]
    assert start.data["spec"]["single_arm"] is True
    assert not (result.run_dir.parent.parent / "ws" / result.ab_id / "bare").exists()


def test_the_record_and_the_score_are_marked_single_arm(course_repo: Path, tmp_path: Path) -> None:
    result, _clients, _deps = harness_only(course_repo, tmp_path)
    data = json.loads((result.run_dir / "ab.json").read_text(encoding="utf-8"))
    assert data["single_arm"] is True
    assert data["mode"] == "harness in action"
    assert set(data["arms"]) == {"harness"}
    [score] = read_exports("scores", tmp_path / "exports")
    assert score["single_arm"] is True and score["arm"] == "harness"
    assert result.arms["harness"].record.single_arm is True


def test_the_run_folder_names_its_section_from_the_start(course_repo: Path, tmp_path: Path) -> None:
    # The console's run list reads start.json while the run goes on (ab.json comes at the end).
    result, _clients, _deps = harness_only(course_repo, tmp_path)
    start = json.loads((result.run_dir / "start.json").read_text(encoding="utf-8"))
    assert start == {
        "ab_id": result.ab_id,
        "section": "demo-1",
        "mode": "harness in action",
        "feature_id": "F1",
        "single_arm": True,
        "constructed": False,
    }


def test_a_two_arm_ab_is_not_single_arm_and_records_its_profile(
    course_repo: Path, tmp_path: Path
) -> None:
    deps = make_deps(course_repo, tmp_path, Clients(), profile="class")
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    data = json.loads((result.run_dir / "ab.json").read_text(encoding="utf-8"))
    assert (data["single_arm"], data["mode"], data["profile"]) == (False, "A/B", "class")
    assert {a["spec"]["profile"] for a in data["arms"].values()} == {"class"}
    assert {s["single_arm"] for s in read_exports("scores", tmp_path / "exports")} == {False}


def test_swap_latest_skips_single_arm_records_and_refuses_one_by_id(
    course_repo: Path, tmp_path: Path
) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    task = ABTask.from_dataset_line(LINE)
    both = run_ab(task, frozenset({"instructions"}), deps, section="demo-1")
    single = run_ab(task, frozenset({"instructions"}), deps, section="demo-1", arms=("harness",))
    assert latest_ab_dir(tmp_path / "runs", "demo-1") == both.run_dir
    recorded = RecordedDeps(
        course_repo=course_repo,
        referee_sandbox_factory=Factory(all_green()),
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    with pytest.raises(SingleArmRecord, match="single-arm"):
        run_swap(single.run_dir, recorded)


def test_a_replay_of_a_single_arm_run_stays_single_arm(course_repo: Path, tmp_path: Path) -> None:
    result, _clients, _deps = harness_only(course_repo, tmp_path)
    recorded = RecordedDeps(
        course_repo=course_repo,
        referee_sandbox_factory=Factory(all_green()),
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    out = replay_ab(result.run_dir, recorded)
    assert set(out.records) == {"harness"}
    assert out.records["harness"].single_arm is True
    replayed = [s for s in read_exports("scores", tmp_path / "exports") if s["recorded"]]
    assert [s["single_arm"] for s in replayed] == [True]


def test_the_ab_report_leaves_single_arm_records_out(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    for i, (arm, single) in enumerate([("bare", False), ("harness", False), ("harness", True)]):
        rec = record(run_id=f"r-{i}", arm=arm, primary={"r1_new_violations": 0}, single_arm=single)
        write_export("scores", rec.run_id, rec, exports)
    report = build_report(exports)
    assert report["runs"] == 2
    [group] = report["groups"]
    assert {arm: len(info["dots"]) for arm, info in group["arms"].items()} == {
        "bare": 1,
        "harness": 1,
    }


def test_screen_4_leaves_single_arm_records_out_and_counts_them(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    for i, (arm, single) in enumerate([("bare", False), ("harness", False), ("harness", True)]):
        rec = record(run_id=f"r-{i}", arm=arm, single_arm=single)
        write_export("scores", rec.run_id, rec, exports)
    report = load_report(exports)
    assert [(g.arm, len(g.dots)) for g in report.groups] == [("bare", 1), ("harness", 1)]
    assert report.single_arm == 1
    assert {c.arm: c.spent_usd for c in report.costs}.keys() == {"bare", "harness"}


def test_ab_command_runs_the_harness_arm_alone(env) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    args = ["ab", "--feature", "F1", "--section", "demo-1", "--arms", "harness",
            "--no-preview", "--dataset", str(env.dataset)]  # fmt: skip
    result = CliRunner().invoke(make_app(), args)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    [header] = [line for line in lines if line.startswith("A/B ")]
    assert "harness in action" in header and "profile=standard" in header
    records = lines[lines.index(header) + 1 : -1]
    assert [line.split()[0] for line in records] == ["harness"]


def test_ab_command_refuses_an_unknown_arms_value(env) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    args = ["ab", "--feature", "F1", "--arms", "bare", "--dataset", str(env.dataset)]
    line = _one_line_error(CliRunner().invoke(make_app(), args))
    assert "--arms" in line and "both" in line and "harness" in line


def test_the_test_cap_is_refused_for_an_ab(env) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    args = ["ab", "--feature", "F4", "--max-tests", "3", "--dataset", str(env.dataset)]
    line = _one_line_error(CliRunner().invoke(make_app(), args))
    assert "--max-tests" in line and "never for an A/B" in line


def test_swap_of_a_single_arm_run_by_id_is_one_line(env) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    app = make_app()
    args = ["ab", "--feature", "F1", "--section", "demo-1", "--arms", "harness",
            "--no-preview", "--dataset", str(env.dataset)]  # fmt: skip
    first = CliRunner().invoke(app, args)
    ab_id = next(line.split()[1] for line in first.output.splitlines() if line.startswith("A/B "))
    line = _one_line_error(CliRunner().invoke(app, ["ab", "--swap", ab_id]))
    assert "single-arm" in line
