"""CLI output in tests is plain text on any host, including GitHub Actions.

On GitHub Actions typer and rich print ANSI colour codes (GITHUB_ACTIONS, FORCE_COLOR) and wrap at
the runner's width, so an assertion such as `"--target" in result.output` failed there while it
passed locally. tests/conftest.py makes the test environment plain (no colour, fixed width); these
tests reproduce the CI conditions and check the result.
"""

from __future__ import annotations

import os

import pytest
import typer.rich_utils
from typer.testing import CliRunner

from shipharness.cli import app
from tests.conftest import PLAIN_CLI_ENV, plain_cli_output
from tests.unit.cli_output import strip_ansi

CI_ENV = {"GITHUB_ACTIONS": "true", "FORCE_COLOR": "1", "COLUMNS": "60"}


def _ci_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment of a GitHub Actions runner, and typer's import-time reading of it."""
    for key, value in CI_ENV.items():
        monkeypatch.setenv(key, value)
    for key in ("NO_COLOR", "TERM", "_TYPER_FORCE_DISABLE_TERMINAL", "TERMINAL_WIDTH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", True)
    monkeypatch.setattr(typer.rich_utils, "MAX_WIDTH", None)


def test_ci_conditions_reproduce_the_colour_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    # The control: without the plain environment, CI conditions split `--target` with ANSI codes.
    _ci_conditions(monkeypatch)
    result = CliRunner().invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "\x1b[" in result.output


def test_init_help_names_target_under_ci_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    _ci_conditions(monkeypatch)
    plain_cli_output(monkeypatch)  # what the autouse fixture in tests/conftest.py applies
    result = CliRunner().invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "\x1b[" not in result.output
    assert "--target" in result.output and "--check" in result.output


def test_the_autouse_fixture_makes_every_test_plain() -> None:
    for key, value in PLAIN_CLI_ENV.items():
        assert os.environ.get(key) == value, key
    assert "FORCE_COLOR" not in os.environ and "PY_COLORS" not in os.environ
    assert typer.rich_utils.FORCE_TERMINAL is False
    result = CliRunner().invoke(app, ["init", "--help"])
    assert "\x1b[" not in result.output and "--target" in result.output


def test_strip_ansi_removes_colour_and_style_codes() -> None:
    assert strip_ansi("\x1b[1;33mUsage:\x1b[0m \x1b[1;36m-\x1b[0m\x1b[1;36m-target\x1b[0m") == (
        "Usage: --target"
    )
    assert strip_ansi("plain") == "plain"
