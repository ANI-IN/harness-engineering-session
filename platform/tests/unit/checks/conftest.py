"""Fixtures for check tests: TeamTrack base copies, seeded-violation builds, module hygiene."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests.unit.checks.seeds import copy_teamtrack


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "browser: needs a Playwright Chromium browser")


@pytest.fixture(autouse=True)
def _restore_app_modules() -> Iterator[None]:
    """Loading a build imports its `app` package; put the bundled TeamTrack modules back after."""
    saved = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
    path = list(sys.path)
    yield
    for name in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[name]
    sys.modules.update(saved)
    sys.path[:] = path


@pytest.fixture
def make_build(tmp_path: Path) -> Callable[[], Path]:
    counter = iter(range(1000))

    def make() -> Path:
        return copy_teamtrack(tmp_path / f"build{next(counter)}")

    return make


@pytest.fixture(scope="session")
def base_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A pristine copy of the TeamTrack base, shared read-only by tests."""
    return copy_teamtrack(tmp_path_factory.mktemp("base") / "teamtrack")


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False
