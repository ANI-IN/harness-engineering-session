"""EventBus: validates events and appends them to a JSONL run log."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from shipharness.events.models import EVENT_DATA_MODELS, Arm, Event, EventType
from shipharness.events.reader import follow_events, read_events
from shipharness.log_setup import redact

__all__ = ["EventBus", "RunLogLocked", "follow_events", "pid_alive", "read_events"]


class RunLogLocked(RuntimeError):
    """Raised when another EventBus already writes to the same run log."""


# A lock file with no pid yet is a writer between create and write; after this long it is a writer
# that died in between.
EMPTY_LOCK_GRACE_S = 30.0


def pid_alive(pid: int) -> bool:
    """True if a process with `pid` exists. Never signals the process (on Windows `os.kill(pid, 0)`
    would terminate it). A recycled pid reads as alive, which keeps the lock: the safe side."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_query_limited_information, still_active, error_access_denied = 0x1000, 259, 5
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return kernel32.GetLastError() == error_access_denied
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_is_stale(lock_path: Path) -> tuple[bool, str]:
    """(stale, content). Stale = the recorded pid is not alive, or no pid was ever written and the
    file is older than EMPTY_LOCK_GRACE_S."""
    try:
        content = lock_path.read_text(encoding="utf-8").strip()
        age = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return True, ""
    if content.isdigit():
        return not pid_alive(int(content)), content
    return age > EMPTY_LOCK_GRACE_S, content


def _reclaim_stale_lock(lock_path: Path) -> bool:
    """Move a stale lock aside. The lock is renamed (atomic) and its content re-checked, so a
    writer that took the lock in the meantime is put back instead of being dropped."""
    stale, content = _lock_is_stale(lock_path)
    if not stale:
        return False
    aside = lock_path.with_name(f"{lock_path.name}.stale-{os.getpid()}-{time.monotonic_ns()}")
    try:
        os.rename(lock_path, aside)
    except FileNotFoundError:
        return True  # already gone
    except OSError:
        return False
    if aside.read_text(encoding="utf-8").strip() != content:
        try:
            os.rename(aside, lock_path)  # someone else's fresh lock: restore it
        except OSError:
            aside.unlink(missing_ok=True)
        return False
    aside.unlink(missing_ok=True)
    return True


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventBus:
    """One writer per run log. Use as a context manager so the lock is released."""

    def __init__(self, log_path: Path, ab_id: str | None) -> None:
        self.log_path = Path(log_path)
        self.ab_id = ab_id
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.log_path.with_name(self.log_path.name + ".lock")
        self._acquire_lock()
        self._mutex = threading.Lock()
        self._listeners: list[Callable[[Event], None]] = []
        self._seq = max((event.seq for event in read_events(self.log_path)), default=0)
        self._closed = False

    def _acquire_lock(self) -> None:
        """Create the lock file holding our pid. A lock left by a writer that is no longer alive
        (hard kill, crash) is reclaimed once; a live writer's lock raises RunLogLocked."""
        for attempt in range(2):
            try:
                fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if attempt == 0 and _reclaim_stale_lock(self._lock_path):
                    continue
                raise RunLogLocked(f"run log already open: {self.log_path}") from None
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return

    def __enter__(self) -> EventBus:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._lock_path.unlink(missing_ok=True)

    def add_listener(self, listener: Callable[[Event], None]) -> None:
        self._listeners.append(listener)

    # [walkthrough:Opening:publish] start
    def publish(
        self,
        type: EventType,
        data: BaseModel | dict[str, Any],
        *,
        run_id: str | None,
        arm: Arm | None,
        recorded: bool = False,
    ) -> Event:
        """Validate `data`, append one JSON line, notify listeners. Every stage of a run goes
        through here; the console streams the same file over SSE."""
        model = EVENT_DATA_MODELS.get(type)
        if model is None:
            raise ValueError(f"unknown event type: {type!r}")
        raw = data.model_dump() if isinstance(data, BaseModel) else data
        raw = redact(raw)  # no key-shaped string or credential field ever reaches a run log
        payload = model.model_validate(raw).model_dump(mode="json")
        with self._mutex:
            if self._closed:
                raise RuntimeError("EventBus is closed")
            self._seq += 1
            event = Event(
                ab_id=self.ab_id,
                run_id=run_id,
                arm=arm,
                seq=self._seq,
                ts=_now(),
                type=type,
                data=payload,
                recorded=recorded,
            )
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        for listener in self._listeners:
            listener(event)
        return event

    # [walkthrough:Opening:publish] end
