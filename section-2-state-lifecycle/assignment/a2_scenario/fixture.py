"""The mini repository every scenario starts from: a TeamTrack-shaped app with one migration.

It has the layout the S2 state layer reads (`migrations/versions/*.py`, `tests/visible/`) and the
same database variable as TeamTrack (`TEAMTRACK_DATABASE_URL`), and it needs no network, Docker,
or keys.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

GIT_ID = ["-c", "user.name=checkpoint", "-c", "user.email=checkpoint@a2.invalid"]

BASE_FILES: dict[str, str] = {
    ".gitignore": "__pycache__/\n*.pyc\n*.db\n.pytest_cache/\n",
    "pytest.ini": "[pytest]\naddopts = -p no:cacheprovider\n",
    "README.md": (
        "# Mini TeamTrack\n\n"
        "A small issue tracker used by assignment A2. Migrations are in migrations/versions/ "
        "(exactly one head), tests in tests/visible/.\n"
    ),
    "alembic.ini": "[alembic]\nscript_location = migrations\n",
    "migrations/env.py": '''"""Alembic environment. The database URL is TEAMTRACK_DATABASE_URL."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

URL = os.environ.get("TEAMTRACK_DATABASE_URL", "sqlite:////tmp/a2-mini-dev.db")


def run_migrations_online() -> None:
    engine = create_engine(URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
''',
    "migrations/versions/0001_initial.py": '''"""Initial schema: issues."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("issues")
''',
    "app/__init__.py": '"""Mini TeamTrack."""\n',
    "app/db.py": '''"""Table metadata shared by the app and the tests."""

import sqlalchemy as sa

metadata = sa.MetaData()

issues = sa.Table(
    "issues",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("title", sa.String(200), nullable=False),
)
''',
    "tests/visible/test_issues.py": '''"""Existing test: the issues table works."""

import sqlalchemy as sa

from app.db import issues, metadata


def test_issues_table_round_trip():
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(issues.insert().values(id=1, title="first"))
        assert conn.execute(sa.select(issues.c.title)).scalar_one() == "first"
''',
}


def git(ws: Path, *args: str) -> str:
    """Host git on a scenario repository (trusted: only this package's code writes to it)."""
    done = subprocess.run(
        ["git", *GIT_ID, *args], cwd=ws, check=True, capture_output=True, text=True
    )
    return done.stdout


def make_repo(ws: Path) -> Path:
    """Create the mini repository at `ws` with one checkpoint commit."""
    ws.mkdir(parents=True, exist_ok=False)
    for rel, text in BASE_FILES.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "checkpoint: mini TeamTrack")
    return ws
