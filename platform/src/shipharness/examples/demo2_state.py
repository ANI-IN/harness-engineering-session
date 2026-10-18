"""Constructed example for section 2 (state and session lifecycle), `make example-2`.

What it demonstrates: a ticket that does not fit in one session. Session 1 has a budget of three
turns: the scripted agent writes the first part of comments on issues (F2: the table, the model, the
repository), commits, and runs out of turns. The state layer then writes the machine summary into
session-handoff.md and a progress.md entry, and commits them (console: session_stop). Session 2
starts with an empty context (console: session_resume), reads session-handoff.md first, and writes
the rest (service, API, seed, board, tests) without redoing session 1's work.

This is a constructed example: the steps below are scripted, no model runs, and it costs $0. It is
never counted with the real runs. The code it applies is the course's reference change for F2,
split across the two sessions.
"""

from __future__ import annotations

from shipharness.examples.base import Scenario, commit, finish, patch, read, reference_patch
from shipharness.runner.model import Step

SESSION_1_FILES = (
    "app/db/models.py",
    "migrations/versions/0002_comments.py",
    "app/repositories/comments.py",
)
SESSION_2_FILES = (
    "app/services/comments.py",
    "app/api/comments.py",
    "app/main.py",
    "app/seed.py",
    "app/web/routes.py",
    "app/web/templates/issue.html",
    "tests/visible/test_comments.py",
)


def steps() -> list[Step]:
    return [
        # Session 1 (3 turns): part of the change, then the turn budget runs out.
        patch(reference_patch("F2", SESSION_1_FILES[:2])),
        patch(reference_patch("F2", SESSION_1_FILES[2:])),
        commit("comments: table, model, and repository"),
        # Session 2 (4 turns): the handoff first, then the rest of the change.
        read("session-handoff.md"),
        patch(reference_patch("F2", SESSION_2_FILES)),
        commit("comments: service, API, seed, board panel, tests"),
        finish(
            "done",
            "Comments on issues: API, seed, and board panel; session 1 built the "
            "table, model, and repository.",
        ),
        finish("done", "Test phase: the comment tests were written in session 2."),
    ]


SCENARIO = Scenario(
    section="demo-2",
    feature="F2",
    title="runs out of turns in session 1, then resumes from session-handoff.md in session 2",
    demonstrates="the state layer writes session-handoff.md and progress.md at the session stop, "
    "and the next session continues from them",
    steps=steps,
    session_budget=(3, 4),
)
