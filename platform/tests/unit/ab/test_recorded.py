from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.ab.demo import ABTask, run_ab
from shipharness.ab.recorded import RecordedDeps, find_run_dir, load_ab, replay_ab, swap_test
from shipharness.events import read_events
from shipharness.tracing import read_exports

from .test_demo import LINE, Clients, make_deps
from .test_referee import Factory, all_green


@pytest.fixture
def finished_ab(course_repo: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    deps = make_deps(course_repo, tmp_path, Clients())
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    return result, deps


def recorded_deps(course_repo: Path, tmp_path: Path, factory: Factory) -> RecordedDeps:
    return RecordedDeps(
        course_repo=course_repo,
        referee_sandbox_factory=factory,
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )


def test_ab_record_has_no_host_paths(finished_ab, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    result, _deps = finished_ab
    text = (result.run_dir / "ab.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in text and str(tmp_path).replace("\\", "/") not in text
    loaded = load_ab(result.run_dir)
    assert set(loaded.arms) == {"bare", "harness"}
    assert loaded.task.feature_id == "F1"


def test_find_run_dir_by_ab_or_run_id(finished_ab, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    result, _deps = finished_ab
    runs = tmp_path / "runs"
    assert find_run_dir(runs, result.ab_id) == result.run_dir
    run_id = result.arms["harness"].spec.run_id
    assert find_run_dir(runs, run_id) == result.run_dir
    with pytest.raises(FileNotFoundError):
        find_run_dir(runs, "r-nothing")


def test_swap_test_gives_identical_judged_measures(
    finished_ab, course_repo: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    result, _deps = finished_ab
    before = read_exports("scores", tmp_path / "exports")
    report = swap_test(result.run_dir, recorded_deps(course_repo, tmp_path, Factory(all_green())))
    assert report.identical, report.differences
    assert report.swapped["bare"].arm == "harness"
    assert read_exports("scores", tmp_path / "exports") == before  # swap records are not runs


def test_swap_test_reports_a_label_sensitive_referee(
    finished_ab, course_repo: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    class LabelSensitive(Factory):
        def __call__(self, build, mounts, arm):  # type: ignore[no-untyped-def]
            self.results = all_green(r1_tenant={"new_violations": 1 if arm == "bare" else 0})
            return super().__call__(build, mounts, arm)

    result, _deps = finished_ab
    report = swap_test(result.run_dir, recorded_deps(course_repo, tmp_path, LabelSensitive([])))
    assert not report.identical
    assert "r1_new_violations" in report.differences["harness"]  # judged under "bare"


def test_replay_marks_events_recorded_and_rejudges(
    finished_ab, course_repo: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    result, _deps = finished_ab
    out = replay_ab(result.run_dir, recorded_deps(course_repo, tmp_path, Factory(all_green())))
    events = list(read_events(out.run_dir / "events.jsonl"))
    assert out.events_replayed > 0
    assert all(e.recorded for e in events)
    assert {e.arm for e in events if e.type == "verdict"} == {"bare", "harness"}
    # The live referee's primary verdicts (run ids of the replay), marked recorded like the rest.
    replayed = {r.run_id for r in out.records.values()}
    early = [e for e in events if e.type == "primary_verdict" and e.run_id in replayed]
    assert {e.arm for e in early} == {"bare", "harness"} and all(e.recorded for e in early)
    assert all(r.recorded for r in out.records.values())
    scores = read_exports("scores", tmp_path / "exports")
    assert sum(1 for s in scores if s["recorded"]) == 2
    assert sum(1 for s in scores if not s["recorded"]) == 2  # originals untouched


def test_ab_record_names_its_section(course_repo: Path, tmp_path: Path) -> None:
    import json

    deps = make_deps(course_repo, tmp_path, Clients())
    result = run_ab(
        ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps, section="demo-1"
    )
    data = json.loads((result.run_dir / "ab.json").read_text(encoding="utf-8"))
    assert data["section"] == "demo-1"


def _fake_ab(runs: Path, ab_id: str, section: str | None) -> Path:
    import json

    run_dir = runs / ab_id
    run_dir.mkdir(parents=True)
    (run_dir / "ab.json").write_text(json.dumps({"section": section, "arms": {}}), encoding="utf-8")
    return run_dir


def test_latest_ab_for_a_section_is_the_newest_one(tmp_path: Path) -> None:
    from shipharness.ab.recorded import latest_ab_dir

    runs = tmp_path / "runs"
    _fake_ab(runs, "ab-20261016-090000-aaaaaa", "demo-2")
    newest = _fake_ab(runs, "ab-20261016-110000-bbbbbb", "demo-2")
    _fake_ab(runs, "ab-20261016-120000-cccccc", "demo-3")  # newer, other section
    _fake_ab(runs, "ab-20261016-130000-dddddd", None)  # recorded before sections were kept
    assert latest_ab_dir(runs, "demo-2") == newest
    assert latest_ab_dir(runs, None).name == "ab-20261016-130000-dddddd"


def test_latest_ab_without_a_match_is_a_clear_error(tmp_path: Path) -> None:
    from shipharness.ab.recorded import latest_ab_dir

    runs = tmp_path / "runs"
    _fake_ab(runs, "ab-20261016-090000-aaaaaa", "demo-1")
    with pytest.raises(FileNotFoundError, match="demo-4"):
        latest_ab_dir(runs, "demo-4")


def test_find_run_dir_resolves_latest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _fake_ab(runs, "ab-20261016-090000-aaaaaa", "demo-1")
    newest = _fake_ab(runs, "ab-20261016-100000-bbbbbb", "demo-1")
    assert find_run_dir(runs, "latest", section="demo-1") == newest
