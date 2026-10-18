from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True, scope="session")
def _fast_child_pytest() -> Iterator[None]:
    """Child pytest processes started through LocalSandbox inherit the environment. The dev
    environment has heavy pytest plugins (hypothesis, schemathesis, langsmith) that the trusted
    fixture repos and TeamTrack's visible tests do not use; skipping their autoload saves about
    two seconds per child run."""
    names = ("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTHONDONTWRITEBYTECODE")
    old = {name: os.environ.get(name) for name in names}
    os.environ.update(dict.fromkeys(names, "1"))
    yield
    for name, value in old.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
