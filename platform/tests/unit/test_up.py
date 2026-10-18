from __future__ import annotations

import sqlite3
from pathlib import Path

from shipharness.teamtrack_host import prepare_database


def test_prepare_database_migrates_and_seeds(tmp_path: Path) -> None:
    db = tmp_path / "teamtrack.db"
    prepare_database(db)
    with sqlite3.connect(db) as connection:
        orgs = connection.execute("select slug from orgs order by id").fetchall()
        version = connection.execute("select version_num from alembic_version").fetchall()
    assert orgs == [("acme",), ("globex",)]
    assert version == [("0001_initial",)]


def test_prepare_database_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "teamtrack.db"
    prepare_database(db)
    prepare_database(db)
    with sqlite3.connect(db) as connection:
        assert connection.execute("select count(*) from orgs").fetchone() == (2,)
