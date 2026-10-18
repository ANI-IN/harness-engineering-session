"""Test-wide setup: plain CLI output, and the `slow` marker for long validations.

Plain CLI output: on GitHub Actions typer and rich print ANSI colour codes (GITHUB_ACTIONS,
FORCE_COLOR) and wrap help text at the runner's width, so `"--target" in result.output` failed
there and passed locally. The session fixture below gives every test, and every subprocess a test
starts, an environment without colour and with a fixed width: NO_COLOR=1, TERM=dumb, COLUMNS=200,
TERMINAL_WIDTH=200 (typer's width), _TYPER_FORCE_DISABLE_TERMINAL=1 (typer ignores GITHUB_ACTIONS
and FORCE_COLOR), and no FORCE_COLOR or PY_COLORS (rich and pytest would force colour). typer reads
its settings once at import, so the fixture also sets them on typer.rich_utils.

The `slow` marker keeps the default run (`uv run pytest`, `make test`) fast.
pyproject addopts deselects `slow`; `make test-all` (`-m "not live and not docker"`) runs them.
Each entry is a node id or node id prefix relative to the repository root. Keep the list explicit:
add a test here only when it is a long validation (roughly > 10 s on its own), and say why.

Already marked `slow` in their own files (not repeated here):
- platform/tests/unit/datasets/test_features_controls.py: the referee on each control's reference,
  hidden tests on the start checkpoint, and referee mutants killed by the reference tests (C1-C8).
- platform/tests/unit/datasets/test_testgen_libs.py: every mutant against the pinned boltons and
  WTForms suites (skipped when .shipharness/libs is absent).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

PLAIN_CLI_ENV: dict[str, str] = {
    "NO_COLOR": "1",
    "TERM": "dumb",
    "COLUMNS": "200",
    "TERMINAL_WIDTH": "200",
    "_TYPER_FORCE_DISABLE_TERMINAL": "1",
}
COLOUR_FORCING_ENV = ("FORCE_COLOR", "PY_COLORS", "CLICOLOR_FORCE", "TTY_COMPATIBLE")


def plain_cli_output(mp: pytest.MonkeyPatch) -> None:
    """No colour codes and a fixed width for CLI output, whatever the host (CI included)."""
    import typer.rich_utils

    for key, value in PLAIN_CLI_ENV.items():
        mp.setenv(key, value)
    for key in COLOUR_FORCING_ENV:
        mp.delenv(key, raising=False)
    mp.setattr(typer.rich_utils, "FORCE_TERMINAL", False)
    mp.setattr(typer.rich_utils, "MAX_WIDTH", int(PLAIN_CLI_ENV["TERMINAL_WIDTH"]))


@pytest.fixture(scope="session", autouse=True)
def _plain_cli_output() -> Iterator[None]:
    """Session-wide, so module and session fixtures that run a CLI see it too."""
    mp = pytest.MonkeyPatch()
    plain_cli_output(mp)
    yield
    mp.undo()


SLOW_TESTS: tuple[str, ...] = (
    # Mutant kill check: the TeamTrack visible suite against every filter and referee mutant.
    "platform/tests/unit/filters/test_teamtrack_mutants.py::test_visible_suite_kills_every_mutant",
    # Full TeamTrack check run: the regression check runs the whole visible suite on the base.
    "platform/tests/unit/checks/test_pytest_checks.py::test_regression_base_keeps_every_visible_test_passing",
    # Full TeamTrack check run: these three share a module fixture that runs the checks runner
    # with R1-R7 and the board on the TeamTrack base.
    "platform/tests/unit/checks/test_runner.py::test_teamtrack_base_has_no_new_violations_except_the_legacy_r1_leak",
    "platform/tests/unit/checks/test_runner.py::test_progress_lines_on_stderr_are_json",
    "platform/tests/unit/checks/test_runner.py::test_baseline_marks_the_legacy_leak_and_exits_zero",
)


def _is_slow(nodeid: str) -> bool:
    return any(nodeid == p or nodeid.startswith((f"{p}[", f"{p}::")) for p in SLOW_TESTS)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Add the `slow` marker before pytest's own -m deselection sees the items."""
    for item in items:
        if _is_slow(item.nodeid):
            item.add_marker(pytest.mark.slow)
