"""Host-side board preview: drives `board_capture` in the preview container through the Sandbox
interface and turns each new frame into a `screenshot` event.

The preview container runs agent-written code, so its output is untrusted: the capture line is
parsed strictly (known view and marks, integer-like issue ids, real PNG bytes, size cap), the
file name is chosen here, and nothing from the output reaches a path or a shell.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import shlex
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shipharness.console.board_capture import (
    DEFAULT_BASE_URL,
    DEFAULT_ORG,
    DEFAULT_USER,
    MARKER,
    MARKS,
)
from shipharness.events import Arm, Event, EventBus
from shipharness.sandbox.base import Sandbox

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
VIEWS = ("board", "issue", "conflict")
MAX_OVERLAYS = 500
_ISSUE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MODULE = "shipharness.console.board_capture"
SERVER_LOG = "/tmp/preview-server.log"


class CaptureError(RuntimeError):
    """The preview container's output was missing, malformed, or unsafe."""


@dataclass(frozen=True)
class Capture:
    view: str
    overlays: list[dict[str, Any]]
    png: bytes


def _issue_id(value: object) -> int | str:
    if isinstance(value, bool):
        raise CaptureError("issue_id must be an integer or a short id")
    if isinstance(value, int):
        return value
    text = str(value)
    if not _ISSUE_ID.match(text):
        raise CaptureError(f"invalid issue_id: {text[:40]!r}")
    return int(text) if text.isdigit() else text


def parse_capture_output(output: str, *, max_png_bytes: int = 8_000_000) -> Capture:
    """Validate the last `SHIPHARNESS-CAPTURE` line of combined container output."""
    lines = [line for line in output.splitlines() if line.startswith(MARKER)]
    if not lines:
        raise CaptureError("no capture line in the preview output")
    try:
        payload = json.loads(lines[-1][len(MARKER) :])
    except ValueError as exc:
        raise CaptureError(f"capture line is not JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise CaptureError("capture line is not JSON object")
    view = payload.get("view")
    if view not in VIEWS:
        raise CaptureError(f"unknown view: {str(view)[:40]!r}")
    raw_overlays = payload.get("overlays")
    if not isinstance(raw_overlays, list) or len(raw_overlays) > MAX_OVERLAYS:
        raise CaptureError("overlays must be a list of at most 500 items")
    overlays: list[dict[str, Any]] = []
    for item in raw_overlays:
        if not isinstance(item, dict) or item.get("mark") not in MARKS:
            raise CaptureError(f"unknown overlay mark: {str(item)[:60]!r}")
        overlays.append({"issue_id": _issue_id(item.get("issue_id")), "mark": item["mark"]})
    encoded = payload.get("png_b64")
    if not isinstance(encoded, str):
        raise CaptureError("png_b64 missing")
    if len(encoded) > (max_png_bytes * 4) // 3 + 8:
        raise CaptureError("screenshot too large")
    try:
        png = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise CaptureError("png_b64 is not valid base64") from None
    if not png.startswith(PNG_MAGIC):
        raise CaptureError("screenshot is not a PNG")
    if len(png) > max_png_bytes:
        raise CaptureError("screenshot too large")
    return Capture(view, overlays, png)


class BoardPreview:
    """One per arm. `start_server()` once, then `capture()` on demand or `run()` every 5 s."""

    def __init__(
        self,
        sandbox: Sandbox,
        bus: EventBus,
        run_dir: Path,
        *,
        run_id: str,
        arm: Arm,
        user: str = DEFAULT_USER,
        org: str = DEFAULT_ORG,
        base_url: str = DEFAULT_BASE_URL,
        app_dir: str = "/work",
        db_path: str = "/tmp/preview.db",
        port: int = 8000,
        python: str = "python",
        timeout_s: int = 90,
        max_png_bytes: int = 8_000_000,
    ) -> None:
        self.sandbox = sandbox
        self.bus = bus
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.arm = arm
        self.user = user
        self.org = org
        self.base_url = base_url
        self.app_dir = app_dir
        self.db_path = db_path
        self.port = port
        self.python = python
        self.timeout_s = timeout_s
        self.max_png_bytes = max_png_bytes
        self.last_error = ""
        self._counters: dict[str, int] = {}
        self._last_digest: dict[str, str] = {}
        self._lock = threading.Lock()

    def _module(self, *args: str) -> str:
        quoted = " ".join(shlex.quote(a) for a in args)
        return f"env HOME=/tmp {shlex.quote(self.python)} -m {MODULE} {quoted}"

    def start_server(self, ready_timeout_s: int = 60) -> None:
        """Start the arm's TeamTrack in the container (detached), then wait for /health."""
        serve = self._module(
            "serve", "--app-dir", self.app_dir, "--db", self.db_path, "--port", str(self.port)
        )
        self.sandbox.exec(f"cd /tmp && nohup {serve} > {SERVER_LOG} 2>&1 < /dev/null &", 30)
        wait = self._module("wait", "--base-url", self.base_url, "--timeout", str(ready_timeout_s))
        result = self.sandbox.exec(wait, ready_timeout_s + 15)
        if result.exit_code != 0:
            log = self.sandbox.exec(f"tail -n 20 {SERVER_LOG}", 10).output
            raise CaptureError(f"preview app did not start: {log[-1000:]}")

    def capture(self, view: str = "board") -> Event | None:
        """Take one frame. Returns the `screenshot` event, or None when the frame is unchanged
        or the capture failed (reason in `last_error`)."""
        with self._lock:
            command = self._module(
                "once",
                "--base-url",
                self.base_url,
                "--user",
                self.user,
                "--org",
                self.org,
                "--view",
                view,
            )
            try:
                result = self.sandbox.exec(command, self.timeout_s)
                if result.exit_code != 0:
                    raise CaptureError(f"capture failed (exit {result.exit_code})")
                shot = parse_capture_output(result.output, max_png_bytes=self.max_png_bytes)
                if shot.view != view:
                    raise CaptureError(f"asked for view {view}, got {shot.view}")
            except CaptureError as exc:
                self.last_error = str(exc)
                return None
            digest = hashlib.sha256(
                shot.png + json.dumps(shot.overlays, sort_keys=True).encode()
            ).hexdigest()
            if self._last_digest.get(view) == digest:
                return None
            self._last_digest[view] = digest
            number = self._counters.get(view, 0) + 1
            self._counters[view] = number
            relative = Path("screenshots") / self.arm / f"{view}-{number:04d}.png"
            target = self.run_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".png.part")
            partial.write_bytes(shot.png)
            os.replace(partial, target)
            self.last_error = ""
            return self.bus.publish(
                "screenshot",
                {
                    "path": relative.as_posix(),
                    "view": view,
                    "as_user": self.user,
                    "overlays": shot.overlays,
                },
                run_id=self.run_id,
                arm=self.arm,
            )

    def run(self, stop: threading.Event, interval_s: float = 5.0) -> int:
        """Capture the board every `interval_s` until `stop` is set; returns events emitted."""
        emitted = 0
        while True:
            started = time.monotonic()
            if self.capture("board") is not None:
                emitted += 1
            if stop.wait(max(0.0, interval_s - (time.monotonic() - started))):
                return emitted
