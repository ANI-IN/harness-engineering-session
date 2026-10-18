"""Every container a DockerSandbox starts is removed: after a failed start, at stop(), and at
process exit for a container whose owner never reached its own stop() (a daemon thread killed at
exit)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import Settings
from shipharness.sandbox import DockerSandbox, default_policy
from shipharness.sandbox import docker as docker_module


class Runner:
    """Answers `docker run` with `run` (a result, or an exception to raise); everything else 0."""

    def __init__(self, run: Any = None) -> None:
        self.run = run if run is not None else subprocess.CompletedProcess([], 0, "abc123\n", "")
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if argv[1] == "run":
            if isinstance(self.run, BaseException):
                raise self.run
            return self.run
        return subprocess.CompletedProcess(argv, 0, "", "")

    def removed(self) -> list[str]:
        return [argv[3] for argv in self.calls if argv[1:3] == ["rm", "-f"]]


def make_box(tmp_path: Path, runner: Runner) -> DockerSandbox:
    policy = default_policy(Settings(_env_file=None))
    return DockerSandbox(policy, "img:1", tmp_path, None, "r-1", "harness", runner=runner)


def test_a_failed_start_removes_the_container(tmp_path: Path) -> None:
    runner = Runner(subprocess.CompletedProcess([], 125, "", "port is already allocated"))
    box = make_box(tmp_path, runner)
    with pytest.raises(RuntimeError, match="run failed"):
        box.start()
    assert runner.removed() == [box.name]  # a created-but-failed container is removed too
    assert box.name not in docker_module.live_containers()


def test_a_start_that_times_out_removes_the_container(tmp_path: Path) -> None:
    runner = Runner(subprocess.TimeoutExpired(["docker", "run"], 120))
    box = make_box(tmp_path, runner)
    with pytest.raises(subprocess.TimeoutExpired):
        box.start()
    assert runner.removed() == [box.name]  # the container may still come up after the timeout
    assert box.name not in docker_module.live_containers()


def test_stop_all_removes_only_the_containers_never_stopped(tmp_path: Path) -> None:
    runner = Runner()
    left, stopped = make_box(tmp_path, runner), make_box(tmp_path, runner)
    left.start()
    stopped.start()
    assert {left.name, stopped.name} <= set(docker_module.live_containers())
    stopped.stop()
    runner.calls.clear()
    docker_module.stop_all()
    assert runner.removed() == [left.name]
    docker_module.stop_all()
    assert runner.removed() == [left.name]  # removed once; nothing left to remove


CHILD = textwrap.dedent(
    """
    import sys
    import threading
    from pathlib import Path
    from subprocess import CompletedProcess

    from shipharness.config import Settings
    from shipharness.sandbox import DockerSandbox, default_policy

    log = Path(sys.argv[1])

    def runner(argv, **_kw):
        with log.open("a", encoding="utf-8") as out:
            out.write(" ".join(argv[:4]) + "\\n")
        if argv[1] == "exec":
            threading.Event().wait()  # a capture still running when the process exits
        return CompletedProcess(argv, 0, "abc123\\n", "")

    policy = default_policy(Settings(_env_file=None))
    box = DockerSandbox(policy, "img:1", Path(sys.argv[2]), None, "r-1", "harness", runner=runner)
    started = threading.Event()

    def work():
        box.start()
        started.set()
        try:
            box.exec("sleep 600", 600)
        finally:
            box.stop()  # never reached: the daemon thread dies with the process

    threading.Thread(target=work, daemon=True).start()
    started.wait(30)
    print(box.name)
    """
)


def test_process_exit_removes_a_container_a_daemon_thread_never_stopped(tmp_path: Path) -> None:
    """The 2026-10-17 leak: the board preview thread was still capturing when `make show-4`
    exited, so its `finally: sandbox.stop()` never ran and the container kept running."""
    log = tmp_path / "docker.log"
    child = subprocess.run(
        [sys.executable, "-c", CHILD, str(log), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert child.returncode == 0, child.stderr[-2000:]
    name = child.stdout.strip()
    assert name.startswith("shipharness-harness-")
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("docker run")
    assert f"docker rm -f {name}" in lines
