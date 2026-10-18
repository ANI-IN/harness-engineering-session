"""Legacy /v1 behaviour (documented), migrations (R7), and layering (R6)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from conftest import auth

TEAMTRACK = Path(__file__).resolve().parents[2]


def test_v1_issues_returns_a_bare_array(client, acme) -> None:
    response = client.get("/v1/issues?limit=5", headers=auth(acme.admin))
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_v1_legacy_is_not_tenant_filtered_documented_bug(client, acme, globex) -> None:
    """Documents current behaviour: the legacy handler predates tenant isolation (see docs)."""
    rows = client.get("/v1/issues?limit=100", headers=auth(acme.admin)).json()
    assert globex.org_id in {row["org_id"] for row in rows}


def test_v1_requires_auth(client) -> None:
    assert client.get("/v1/issues").status_code == 401


def alembic_config(db_url: str) -> Config:
    config = Config(str(TEAMTRACK / "alembic.ini"))
    config.set_main_option("script_location", str(TEAMTRACK / "migrations"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def test_upgrade_head_on_empty_database(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    command.upgrade(alembic_config(url), "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {
        "orgs",
        "users",
        "projects",
        "project_members",
        "issues",
        "audit_log",
        "idempotency_keys",
    } <= tables


def test_single_migration_head() -> None:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    assert len(script.get_heads()) == 1


def test_migration_matches_models(tmp_path: Path) -> None:
    from app.db.base import Base

    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    command.upgrade(alembic_config(url), "head")
    inspector = inspect(create_engine(url))
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"] for c in inspector.get_columns(table.name)}
        assert migrated == {c.name for c in table.columns}, table.name


def test_api_never_imports_db() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--config",
            str(TEAMTRACK / ".importlinter"),
        ],
        cwd=TEAMTRACK,
        env={**os.environ, "PYTHONUTF8": "1"},
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert "Contracts: 2 kept, 0 broken." in result.stdout, result.stdout + result.stderr
    assert result.returncode == 0
