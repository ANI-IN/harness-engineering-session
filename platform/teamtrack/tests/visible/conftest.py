"""Shared fixtures: a fresh seeded TeamTrack app per test, and per-user auth headers."""

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


def auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer tt-{user_id}"}


@pytest.fixture
def acme() -> SeedOrg:
    return ACME


@pytest.fixture
def globex() -> SeedOrg:
    return GLOBEX


def error_code(response) -> str:  # type: ignore[no-untyped-def]
    body = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message"}, body
    return body["error"]["code"]
