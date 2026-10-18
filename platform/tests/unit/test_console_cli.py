"""`shipharness console` is quiet by default: no line per request, only warnings and errors.

`--verbose` (`make console VERBOSE=1`) restores uvicorn's access log and info logs. The tests
capture the arguments given to uvicorn.run instead of starting a server.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import uvicorn
from typer.testing import CliRunner

from shipharness import cli


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    def fake_run(app: Any, **kwargs: Any) -> None:
        calls["app"] = app
        calls.update(kwargs)

    settings = SimpleNamespace(runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports")
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(uvicorn, "run", fake_run)
    return calls


def test_console_is_quiet_by_default(captured: dict[str, Any]) -> None:
    result = CliRunner().invoke(cli.app, ["console", "--port", "8799"])
    assert result.exit_code == 0, result.output
    assert captured["access_log"] is False
    assert captured["log_level"] == "warning"
    assert captured["host"] == "127.0.0.1" and captured["port"] == 8799
    assert "Console: http://127.0.0.1:8799/" in result.output  # the address to open still prints
    assert "--verbose" in result.output  # and how to get the request log back


def test_console_verbose_restores_the_access_log(captured: dict[str, Any]) -> None:
    result = CliRunner().invoke(cli.app, ["console", "--port", "8799", "--verbose"])
    assert result.exit_code == 0, result.output
    assert captured["access_log"] is True
    assert captured["log_level"] == "info"
    assert "Console: http://127.0.0.1:8799/" in result.output


@pytest.mark.parametrize(
    ("verbose", "access_log", "level"), [(False, False, "warning"), (True, True, "info")]
)
def test_console_server_options(verbose: bool, access_log: bool, level: str) -> None:
    assert cli.console_server_options(verbose) == {"access_log": access_log, "log_level": level}
