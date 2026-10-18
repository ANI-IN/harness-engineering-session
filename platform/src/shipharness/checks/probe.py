"""In-process probes against a TeamTrack build (no network; runs in the referee container)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def load_app(build_dir: Path, db_path: Path) -> Any:
    """Import `app.main` from `build_dir` and create a seeded app on a fresh SQLite file.

    Executes the build's code, so the referee calls this only inside its own container.
    """
    root = str(Path(build_dir).resolve())
    for name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[name]
    sys.path.insert(0, root)
    try:
        main = importlib.import_module("app.main")
        settings_module = importlib.import_module("app.settings")
        settings = settings_module.TeamTrackSettings(
            database_url=f"sqlite:///{Path(db_path).as_posix()}", create_schema=True, seed=True
        )
        return main.create_app(settings)
    finally:
        sys.path.remove(root)


class ProbeClient:
    """HTTP client bound to one seeded user (demo token `tt-<id>`)."""

    def __init__(self, app: Any, user_id: int) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers = {"Authorization": f"Bearer tt-{user_id}"}

    def request(
        self,
        method: str,
        path: str,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self.client.request(
            method, path, json=json, headers={**self.headers, **(headers or {})}
        )


def fill_path(path: str, values: dict[str, int]) -> str:
    """Substitute `{name}` path parameters (see `shipharness.checks.payloads.fill_path`)."""
    from shipharness.checks.payloads import fill_path as _fill

    return _fill(path, values)
