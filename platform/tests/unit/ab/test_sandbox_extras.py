"""Sandbox additions for M4: extra read-only mounts (referee) and exit 124 / 137 classification."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import Settings
from shipharness.sandbox import DockerSandbox, default_policy, docker_run_args


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def test_extra_mounts_are_added_with_their_mode(settings: Settings, tmp_path: Path) -> None:
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    args = docker_run_args(
        default_policy(settings),
        "img:1",
        tmp_path,
        "n",
        extra_mounts=[(hidden, "/hidden", "ro")],
    )
    assert f"{hidden.resolve()}:/hidden:ro" in args
    assert args.index(f"{hidden.resolve()}:/hidden:ro") < args.index("img:1")


def test_read_only_mount_inside_the_workspace_is_allowed(
    settings: Settings, tmp_path: Path
) -> None:
    args = docker_run_args(
        default_policy(settings),
        "img:1",
        tmp_path,
        "n",
        extra_mounts=[(tmp_path, "/work/tests/hidden", "ro")],
    )
    assert f"{tmp_path.resolve()}:/work/tests/hidden:ro" in args


def test_no_extra_mounts_by_default(settings: Settings, tmp_path: Path) -> None:
    args = docker_run_args(default_policy(settings), "img:1", tmp_path, "n")
    assert [a for a in args if a.endswith(":ro")] == []


@pytest.mark.parametrize(
    "mount",
    [
        ("{tmp}", "/work", "ro"),  # would shadow the workspace mount
        ("{tmp}", "/", "ro"),  # above the workspace
        ("{tmp}", "/work/tests/hidden", "rw"),  # inside the workspace: read-only only
        ("{tmp}", "relative/path", "ro"),
        ("{tmp}", "/hidden", "rwx"),
        ("{tmp}", "/hidden:rw", "ro"),
    ],
)
def test_bad_extra_mounts_are_refused(
    settings: Settings, tmp_path: Path, mount: tuple[str, str, str]
) -> None:
    host, container, mode = mount
    with pytest.raises(ValueError):
        docker_run_args(
            default_policy(settings),
            "img:1",
            tmp_path,
            "n",
            extra_mounts=[(Path(host.format(tmp=tmp_path)), container, mode)],  # type: ignore[list-item]
        )


def test_docker_sandbox_passes_extra_mounts_to_run(settings: Settings, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"cid\n", b"")

    sandbox = DockerSandbox(
        default_policy(settings),
        "img:1",
        tmp_path,
        None,
        "r-1",
        "bare",
        runner=runner,
        extra_mounts=[(tmp_path, "/hidden", "ro")],
    )
    sandbox.start()
    assert f"{tmp_path.resolve()}:/hidden:ro" in calls[0]


class ScriptedRunner:
    """Fake runtime CLI: `exec` of the tool command returns `exit_code` after `elapsed` seconds
    (on a fake clock); reads of memory.events return successive oom_kill counters."""

    def __init__(self, exit_code: int, elapsed: float, oom_counts: list[int]) -> None:
        self.exit_code = exit_code
        self.elapsed = elapsed
        self.oom_counts = list(oom_counts)
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
        if argv[1] == "exec" and argv[-1].endswith("memory.events"):
            count = self.oom_counts.pop(0) if self.oom_counts else 0
            events = f"oom {count}\noom_kill {count}\n".encode()
            return subprocess.CompletedProcess(argv, 0, events, b"")
        if argv[1] == "exec":
            self.now += self.elapsed
            return subprocess.CompletedProcess(argv, self.exit_code, b"Killed\n", b"")
        return subprocess.CompletedProcess(argv, 0, b"cid\n", b"")


def make(settings: Settings, tmp_path: Path, runner: ScriptedRunner) -> DockerSandbox:
    box = DockerSandbox(
        default_policy(settings),
        "img:1",
        tmp_path,
        None,
        "r-1",
        "bare",
        runner=runner,
        clock=runner.clock,
    )
    box.start()
    return box


Case = tuple[int, float, list[int], bool, str | None]


@pytest.mark.parametrize(
    ("exit_code", "elapsed", "oom_counts", "timed_out", "reason"),
    [
        (124, 10.0, [0, 0], True, "timeout"),  # timeout(1) stopped the command at the limit
        (137, 15.0, [0, 0], True, "timeout"),  # --kill-after sent SIGKILL after the limit
        (137, 1.0, [1], False, "memory"),  # the cgroup OOM killer ended it early
        (137, 1.0, [0], False, None),  # killed by a signal, no OOM kill: not a denial
        (124, 1.0, [0, 0], False, None),  # the command itself exited 124 quickly
    ],
)
def test_exit_124_and_137_are_classified(
    settings: Settings,
    tmp_path: Path,
    exit_code: int,
    elapsed: float,
    oom_counts: list[int],
    timed_out: bool,
    reason: str | None,
) -> None:
    runner = ScriptedRunner(exit_code, elapsed, oom_counts)
    box = make(settings, tmp_path, runner)
    result = box.exec("python big.py", timeout_s=10)
    assert result.timed_out is timed_out
    assert (result.denied.reason_code if result.denied else None) == reason


def test_unreadable_oom_counter_falls_back_to_memory_for_early_137(
    settings: Settings, tmp_path: Path
) -> None:
    def runner(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
        if argv[1] == "exec" and argv[-1].endswith("memory.events"):
            return subprocess.CompletedProcess(argv, 1, b"", b"No such file")
        if argv[1] == "exec":
            return subprocess.CompletedProcess(argv, 137, b"", b"")
        return subprocess.CompletedProcess(argv, 0, b"cid\n", b"")

    clock: Callable[[], float] = lambda: 0.0  # noqa: E731
    box = DockerSandbox(
        default_policy(settings), "img:1", tmp_path, None, "r-1", "bare", runner=runner, clock=clock
    )
    box.start()
    result = box.exec("python big.py", timeout_s=10)
    assert result.denied is not None and result.denied.reason_code == "memory"
