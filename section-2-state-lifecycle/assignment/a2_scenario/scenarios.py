"""The visible feature and scenarios. The grader adds hidden scenarios of the same kinds."""

from __future__ import annotations

from dataclasses import dataclass, field

from a2_scenario.feature import Feature, FileSlot, Step

COMMENTS_MIGRATION = '''"""Comments table."""

import sqlalchemy as sa
from alembic import op

revision = "{rev}"
down_revision = "{down}"


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("body", sa.String(5000), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("comments")
'''

COMMENTS_MODELS = '''"""Comments table definition."""

import sqlalchemy as sa

from app.db import metadata

comments = sa.Table(
    "comments",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id"), nullable=False),
    sa.Column("body", sa.String(5000), nullable=False),
)
'''

COMMENTS_SERVICE = '''"""Add, list, and delete comments."""

import sqlalchemy as sa

from app.comments.models import comments
from app.comments.validation import check_body


def add_comment(conn, issue_id: int, body: str) -> int:
    result = conn.execute(comments.insert().values(issue_id=issue_id, body=check_body(body)))
    return int(result.inserted_primary_key[0])


def list_comments(conn, issue_id: int) -> list[str]:
    query = sa.select(comments.c.body).where(comments.c.issue_id == issue_id)
    return [row.body for row in conn.execute(query.order_by(comments.c.id))]


def delete_comment(conn, comment_id: int) -> bool:
    result = conn.execute(comments.delete().where(comments.c.id == comment_id))
    return result.rowcount == 1
'''

COMMENTS_VALIDATION = '''"""Validation rules for comments."""

MAX_BODY = 5000


def check_body(body: str) -> str:
    text = body.strip()
    if not 1 <= len(text) <= MAX_BODY:
        raise ValueError("body must be 1 to 5000 characters")
    return text
'''

COMMENTS_INDEX = '''"""Index on comments.issue_id."""

from alembic import op

revision = "{rev}"
down_revision = "{down}"


def upgrade() -> None:
    op.create_index("ix_comments_issue_id", "comments", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_issue_id", table_name="comments")
'''

COMMENTS_TESTS = '''"""Tests for the comment service."""

import pytest
import sqlalchemy as sa

from app.comments.service import add_comment, delete_comment, list_comments
from app.db import issues, metadata


@pytest.fixture
def conn():
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(issues.insert().values(id=1, title="first"))
        yield connection


def test_comments_are_listed_oldest_first(conn):
    add_comment(conn, 1, "one")
    add_comment(conn, 1, "two")
    assert list_comments(conn, 1) == ["one", "two"]


def test_an_empty_body_is_rejected(conn):
    with pytest.raises(ValueError):
        add_comment(conn, 1, "   ")


def test_delete_removes_the_comment(conn):
    comment_id = add_comment(conn, 1, "gone soon")
    assert delete_comment(conn, comment_id) is True
    assert list_comments(conn, 1) == []
'''

COMMENTS = Feature(
    id="comments",
    title="Comments on issues",
    summary=(
        "Team members want to discuss an issue on the issue itself. Add a comments table, a "
        "service to add, list, and delete comments, an index for listing, and tests."
    ),
    rev_code="c",
    base_rev="0001",
    steps=(
        Step(
            "S1",
            "Comments table",
            "one migration that creates the comments table, and app/comments/models.py",
            (
                FileSlot("migration", "migrations/versions/{rev}_comments.py", COMMENTS_MIGRATION),
                FileSlot("models", "app/comments/models.py", COMMENTS_MODELS),
            ),
        ),
        Step(
            "S2",
            "Comment service",
            "app/comments/service.py and app/comments/validation.py",
            (
                FileSlot("service", "app/comments/service.py", COMMENTS_SERVICE),
                FileSlot("validation", "app/comments/validation.py", COMMENTS_VALIDATION),
            ),
        ),
        Step(
            "S3",
            "Index and tests",
            "one migration that adds an index on comments.issue_id, and "
            "tests/visible/test_comments.py",
            (
                FileSlot("index", "migrations/versions/{rev}_comment_index.py", COMMENTS_INDEX),
                FileSlot("tests", "tests/visible/test_comments.py", COMMENTS_TESTS),
            ),
        ),
    ),
)


@dataclass(frozen=True)
class Scenario:
    """One run: a feature, the session turn budgets (one per session), and agent behaviours.

    Every scenario has four sessions, so the run is stopped three times by the session turn budget
    before the agent can finish. `behaviours` maps a session index to something the agent does at
    the wrap-up message: "note" (writes a note in session-handoff.md), "clobber" (rewrites
    progress.md), or "tick" (ticks the next step in the exec plan before doing it).
    """

    name: str
    description: str
    feature: Feature
    budgets: tuple[int, ...]
    behaviours: dict[int, str] = field(default_factory=dict)
    wrapup_turns: int = 2


VISIBLE: tuple[Scenario, ...] = (
    Scenario(
        name="V1-boundary-stops",
        description="each stop lands just after a step is committed",
        feature=COMMENTS,
        budgets=(6, 6, 6, 5),
    ),
    Scenario(
        name="V2-mid-step-stops",
        description="each stop lands after a step's files are written but before its commit",
        feature=COMMENTS,
        budgets=(5, 6, 6, 8),
    ),
)
