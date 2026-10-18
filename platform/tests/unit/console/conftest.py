"""Shared fixtures for console tests: the `browser` marker, a Chromium page that skips cleanly
when Playwright's browser is not installed, and a live console server on a free port."""

from __future__ import annotations

import os
import shutil
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "browser: needs a Playwright Chromium (uv run playwright install chromium)"
    )


@pytest.fixture(scope="module")
def chromium() -> Iterator[Any]:
    """A launched headless Chromium, or skip (not fail) when it is unavailable. Module scope:
    the sync Playwright API keeps an event loop running until stopped, which would break
    asyncio.run in later test modules."""
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        manager = sync_api.sync_playwright().start()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Playwright unavailable: {exc}")
    try:
        browser = manager.chromium.launch()
    except Exception as exc:
        manager.stop()
        pytest.skip(f"Chromium not installed (uv run playwright install chromium): {exc}")
    yield browser
    browser.close()
    manager.stop()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LiveServer:
    def __init__(self, app: Any) -> None:
        import uvicorn

        self.port = free_port()
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="warning", timeout_graceful_shutdown=1
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> LiveServer:
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("live server did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *_exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


@pytest.fixture
def live_server() -> Iterator[Callable[[Any], LiveServer]]:
    servers: list[LiveServer] = []

    def start(app: Any) -> LiveServer:
        server = LiveServer(app).__enter__()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.__exit__()


@pytest.fixture
def evidence_dir(tmp_path: Path) -> Callable[[Path], Path]:
    """Save evidence screenshots under tmp; also copy to SHIPHARNESS_EVIDENCE_DIR when set."""
    target = os.environ.get("SHIPHARNESS_EVIDENCE_DIR")

    def keep(path: Path) -> Path:
        if target:
            Path(target).mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, Path(target) / path.name)
        return path

    return keep
