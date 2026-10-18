"""Swap and replay judge the recorded checkpoint commit, never a tag that may have moved since, and
replay counts continuity sessions with the original run ids."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from shipharness.ab.demo import ABTask, run_ab
from shipharness.ab.recorded import (
    RecordedDeps,
    UnpinnedRecord,
    load_ab,
    replay_ab,
    swap_test,
)
from shipharness.checks.continuity import _sessions
from shipharness.runner.model import tool_step
from shipharness.sandbox import ExecResult, FakeSandbox

from ..verify.fakes import runner_output
from .conftest import git, write
from .test_demo import LINE, Clients, make_deps
from .test_referee import Factory, all_green

ORIGINAL_APP = "def create_app():\n    return 'app'\n"
ORIGINAL_HIDDEN = "def test_secret():\n    assert 1\n"


class Capturing(Factory):
    """Records the checkpoint files each referee container was given, and answers the check
    runner with the continuity session count the real check would compute from the params."""

    def __init__(self) -> None:
        super().__init__(all_green())
        self.apps: list[str] = []
        self.hidden: list[str] = []
        self.sessions: dict[str, int | None] = {}

    def __call__(self, build: Path, mounts: list[Any], arm: str) -> FakeSandbox:
        self.calls.append((build, mounts, arm))
        self.apps.append((build / "app" / "main.py").read_text(encoding="utf-8"))
        host = {container: Path(source) for source, container, _mode in mounts}
        hidden_dir = next(p for c, p in host.items() if c.endswith("tests/hidden"))
        self.hidden.append((hidden_dir / "f1" / "test_secret.py").read_text(encoding="utf-8"))
        written: dict[str, str] = {}

        def run(command: str) -> ExecResult:
            if command.startswith("printf %s"):
                parts = command.split()
                written[parts[-1]] = base64.b64decode(parts[2]).decode()
            if "checks.runner" in command:
                params = json.loads(next(v for k, v in written.items() if "params" in k))
                log = params.get("run_log")
                log_host = str(host.get(log, log)) if log else None
                self.sessions[str(params.get("run_id"))] = _sessions(log_host, params["run_id"])
                output = runner_output(self.results, command=command)
                return ExecResult(exit_code=0, output=output, duration_ms=1)
            return self._exec(command)

        box = FakeSandbox(run)
        self.sandboxes.append(box)
        return box


def recorded_deps(course_repo: Path, tmp_path: Path, factory: Factory) -> RecordedDeps:
    return RecordedDeps(
        course_repo=course_repo,
        referee_sandbox_factory=factory,
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )


def move_tag(repo: Path, tag: str) -> str:
    """Commit a different app and hidden test, and move `tag` to that commit."""
    write(repo / "teamtrack" / "app" / "main.py", "MOVED = True\n")
    write(repo / "teamtrack" / "tests" / "hidden" / "f1" / "test_secret.py", "MOVED = True\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "moved")
    git(repo, "tag", "-f", tag)
    return git(repo, "rev-parse", f"{tag}^{{commit}}")


@pytest.fixture
def finished_ab(course_repo: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    deps = make_deps(course_repo, tmp_path, Clients())
    return run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)


def test_ab_record_pins_the_checkpoint_commit(finished_ab, course_repo: Path) -> None:  # type: ignore[no-untyped-def]
    data = json.loads((finished_ab.run_dir / "ab.json").read_text(encoding="utf-8"))
    assert data["checkpoint_sha"] == git(course_repo, "rev-parse", "m1-s1-start^{commit}")
    assert data["from_working_tree"] is False
    assert load_ab(finished_ab.run_dir).checkpoint_sha == data["checkpoint_sha"]


def test_working_tree_ab_records_no_sha_and_says_so(course_repo: Path, tmp_path: Path) -> None:
    deps = make_deps(course_repo, tmp_path, Clients(), checkpoint_ref=None)
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    data = json.loads((result.run_dir / "ab.json").read_text(encoding="utf-8"))
    assert data["checkpoint_sha"] is None
    assert data["from_working_tree"] is True


def test_swap_judges_the_recorded_commit_after_the_tag_moved(
    finished_ab, course_repo: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    move_tag(course_repo, "m1-s1-start")
    factory = Capturing()
    report = swap_test(finished_ab.run_dir, recorded_deps(course_repo, tmp_path, factory))
    assert report.identical, report.differences
    assert factory.apps and set(factory.apps) == {ORIGINAL_APP}
    assert set(factory.hidden) == {ORIGINAL_HIDDEN}


def test_replay_judges_the_recorded_commit_after_the_tag_moved(
    finished_ab, course_repo: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    move_tag(course_repo, "m1-s1-start")
    factory = Capturing()
    replay_ab(finished_ab.run_dir, recorded_deps(course_repo, tmp_path, factory))
    assert factory.apps and set(factory.apps) == {ORIGINAL_APP}
    assert set(factory.hidden) == {ORIGINAL_HIDDEN}


def test_records_without_a_pinned_commit_are_refused(
    finished_ab, course_repo: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    path = finished_ab.run_dir / "ab.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["checkpoint_sha"]
    path.write_text(json.dumps(data), encoding="utf-8")
    factory = Capturing()
    deps = recorded_deps(course_repo, tmp_path, factory)
    with pytest.raises(UnpinnedRecord, match="predates"):
        swap_test(finished_ab.run_dir, deps)
    with pytest.raises(UnpinnedRecord, match="predates"):
        replay_ab(finished_ab.run_dir, deps)
    assert factory.calls == []  # nothing was judged


def test_replay_reports_the_same_continuity_sessions_as_the_original(
    course_repo: Path, tmp_path: Path
) -> None:
    line = json.loads(json.dumps(LINE))
    line["inputs"]["session_budget"] = [1, 6]  # one session stop per arm in the build phase
    steps = [
        tool_step("list_dir", path=".", depth=None),
        tool_step("finish", claim="done", summary="built"),
        tool_step("finish", claim="done", summary="tests"),
    ]
    original = Capturing()
    deps = make_deps(
        course_repo,
        tmp_path,
        Clients(bare=list(steps), harness=list(steps)),
        referee_sandbox_factory=original,
    )
    result = run_ab(ABTask.from_dataset_line(line), frozenset({"instructions"}), deps)
    run_ids = {arm: run.spec.run_id for arm, run in result.arms.items()}
    assert [original.sessions[run_ids[arm]] for arm in ("bare", "harness")] == [1, 1]

    replayed = Capturing()
    replay_ab(result.run_dir, recorded_deps(course_repo, tmp_path, replayed))
    assert sorted(v for k, v in replayed.sessions.items() if k) == [1, 1]
