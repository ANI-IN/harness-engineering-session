"""Deferred minor 13: a run-log lock left behind by a hard-killed writer is reclaimed."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from shipharness.events import EventBus, RunLogLocked, read_events
from shipharness.events.bus import pid_alive


def dead_pid() -> int:
    """A pid that existed a moment ago and has exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def lock_path(log: Path) -> Path:
    return log.with_name(log.name + ".lock")


def test_pid_alive_for_this_process_and_not_for_an_exited_one() -> None:
    assert pid_alive(os.getpid()) is True
    assert pid_alive(dead_pid()) is False


def test_pid_alive_check_never_kills_the_target() -> None:
    # On Windows os.kill(pid, 0) terminates the process; the check must not.
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert pid_alive(proc.pid) is True
        time.sleep(0.2)
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


def test_lock_of_a_dead_writer_is_reclaimed(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    lock_path(log).write_text(str(dead_pid()))
    with EventBus(log, ab_id=None) as bus:
        event = bus.publish(
            "tool_call", {"call_id": "c1", "name": "run", "target": "ls"}, run_id="r", arm="bare"
        )
        assert lock_path(log).read_text() == str(os.getpid())
    assert event.seq == 1
    assert [e.seq for e in read_events(log)] == [1]
    assert not lock_path(log).exists()


def test_lock_of_a_live_writer_is_kept(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_path(log).write_text(str(proc.pid))
        with pytest.raises(RunLogLocked):
            EventBus(log, ab_id=None)
        assert lock_path(log).read_text() == str(proc.pid)
    finally:
        proc.kill()
        proc.wait()


def test_fresh_empty_lock_is_kept_but_an_old_empty_lock_is_reclaimed(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    lock = lock_path(log)
    lock.write_text("")  # writer created the file and has not written its pid yet
    with pytest.raises(RunLogLocked):
        EventBus(log, ab_id=None)
    old = time.time() - 120
    os.utime(lock, (old, old))  # writer died between create and write
    with EventBus(log, ab_id=None):
        assert lock.read_text() == str(os.getpid())
