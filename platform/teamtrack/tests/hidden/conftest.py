"""Fixtures for hidden tests (referee only; never exported into an arm workspace).

Self-contained on purpose: the arm can change tests/visible/conftest.py, so hidden tests never
import from it. Same fixture names as the visible suite: `client`, `acme`, `globex`. Helpers
(`auth`, `error_code`) come from `hidden_support`, never from `conftest`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import ACME, GLOBEX, SeedOrg
from app.settings import TeamTrackSettings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = TeamTrackSettings(
        database_url=f"sqlite:///{(tmp_path / 'teamtrack.db').as_posix()}",
        create_schema=True,
        seed=True,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def acme() -> SeedOrg:
    return ACME


@pytest.fixture
def globex() -> SeedOrg:
    return GLOBEX
