"""Bare-arm content parity.

Every house rule (House rules 1 to 7) and every convention must appear both in docs/HANDBOOK.md
(which both arms read) and in the harness instruction docs. The harness changes how knowledge is
organised, never what the agent can know: every code span the harness docs mention must also be
readable by the bare arm, in the handbook or in the exported repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from shipharness.datasets.names import rule_label
from shipharness.harness.instructions.layer import DEFAULT_SOURCE, source_files

TEAMTRACK = DEFAULT_SOURCE.parents[1]
HANDBOOK = TEAMTRACK / "docs" / "HANDBOOK.md"

# Each rule by its label as both forms write it ("House rule 1: Tenant isolation").
RULES = {code: [rule_label(code)] for code in ("R1", "R2", "R3", "R4", "R5", "R6", "R7")}

# Each convention is a set of phrases; every phrase must appear in both forms.
CONVENTIONS: dict[str, list[str]] = {
    "product": ["multi-tenant issue tracker", "FastAPI", "Jinja2 and HTMX", "Acme", "Globex"],
    "running": [
        "uv sync",
        "alembic upgrade head",
        "uvicorn app.main:create_app --factory --reload",
        "python -m pytest tests/visible -q",
        "POST /auth/login",
        '{"email": "admin@acme.test"}',
        "Authorization: Bearer <token>",
        "not secure",
    ],
    "layout": [
        "app/api/",
        "app/services/",
        "app/repositories/",
        "app/db/",
        "app/web/",
        "Actor",
        "user_id",
        "actor.org_id",
        "app/main.py",
        "app/seed.py",
        "app/api/middleware.py",
        "separate review",
    ],
    "R1 tenant isolation": [
        "org_id",
        "404 not_found",
        "403",
        "as if it did not exist",
        "belongs to the caller's org",
        "Globex IDs",
    ],
    "R2 roles": [
        "admin",
        "member",
        "viewer",
        "403 forbidden",
        "creating and updating users",
        "adding and removing project members",
        "archiving projects",
        "reading the audit log",
        "app/api/deps.py",
        "require_writer",
        "require_admin",
    ],
    "R3 lists": [
        '{"items": [...], "next_cursor": "..." | null}',
        "1 to 100, default 20",
        "app/api/pagination.py",
        "keyset pagination by ascending id",
        "opaque cursor",
        "next_cursor",
        "offset pagination",
    ],
    "R3 errors and status codes": [
        '{"error": {"code": "...", "message": "..."}}',
        "app/services/errors.py",
        "NotFound",
        "Forbidden",
        "Conflict",
        "Invalid",
        "BadRequest",
        "app/api/errors.py",
        "422 validation_error",
        "201",
        "204",
        "200",
        "Schemathesis",
    ],
    "R4 idempotency": [
        "Idempotency-Key",
        "409 idempotency_conflict",
        "per org and per endpoint",
        "services.idempotency.run_once",
        "POST /projects",
        "Issue creation does not support keys yet",
        "exactly one new record",
    ],
    "R5 audit": [
        "exactly one row to the audit log",
        "issue.create",
        "Reads add nothing",
        "idempotent replay adds nothing",
        "services.audit.record",
    ],
    "R6 layering": ["app.db", "import-linter", "lint-imports --config .importlinter"],
    "R7 migrations": [
        "migrations/versions/",
        "exactly one migration head",
        "empty database",
        "alembic heads",
        "down_revision",
        "has not been released",
    ],
    "issues": [
        "open",
        "in_progress",
        "done",
        "low",
        "medium",
        "high",
        "version",
        "invalid_transition",
        "soft delete",
        "deleted_at",
        "Archived projects behave as if they do not exist",
    ],
    "testing": [
        "tests/visible/",
        "tests/visible/conftest.py",
        "client",
        "auth(user_id)",
        "acme",
        "globex",
        "Do not change existing tests",
    ],
    "legacy": [
        "GET /v1/issues",
        "not filtered by org",
        "bare array",
        "scheduled for removal",
        "Do not copy it",
        "repositories.issues.list_all_legacy",
        "services.legacy",
    ],
    "history": [
        "missing rows",
        "append-only",
        "SQLite",
        "Keep queries portable",
        "small pull requests",
    ],
}


def normalise(text: str) -> str:
    text = text.replace("**", "").replace("`", "").replace("’", "'")
    return re.sub(r"\s+", " ", text).lower()


def handbook() -> str:
    return normalise(HANDBOOK.read_text(encoding="utf-8"))


def harness_docs() -> str:
    parts = [
        (DEFAULT_SOURCE / rel).read_text(encoding="utf-8") for rel in source_files(DEFAULT_SOURCE)
    ]
    return normalise("\n".join(parts))


@pytest.mark.parametrize("rule", sorted(RULES))
def test_rule_appears_in_both_forms(rule: str) -> None:
    for phrase in RULES[rule]:
        assert normalise(phrase) in handbook(), f"{rule}: {phrase!r} missing from HANDBOOK.md"
        assert normalise(phrase) in harness_docs(), f"{rule}: {phrase!r} missing from harness docs"


@pytest.mark.parametrize("name", sorted(CONVENTIONS))
def test_convention_appears_in_both_forms(name: str) -> None:
    book, docs = handbook(), harness_docs()
    missing_book = [p for p in CONVENTIONS[name] if normalise(p) not in book]
    missing_docs = [p for p in CONVENTIONS[name] if normalise(p) not in docs]
    assert missing_book == [], f"{name}: missing from HANDBOOK.md"
    assert missing_docs == [], f"{name}: missing from harness docs"


# -- no new facts ----------------------------------------------------------------------------------

_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_EXPORT_SKIP = {"harness", "hidden", "mutants", "reference", "__pycache__"}


def bare_arm_text() -> str:
    """Everything the bare arm can read: the handbook plus the exported repository files."""
    parts = []
    for path in sorted(TEAMTRACK.rglob("*")):
        rel = path.relative_to(TEAMTRACK)
        if not path.is_file() or _EXPORT_SKIP & set(rel.parts) or path.suffix == ".db":
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return normalise("\n".join(parts))


# Folders other harness layers create (M4 contract I-6); docs may point to them conditionally.
OTHER_LAYER_PATHS = ("docs/exec-plans/",)


def is_known_path(span: str) -> bool:
    """A path in the harness tree, a path another layer creates, or one the bare arm has."""
    if span.startswith(OTHER_LAYER_PATHS):
        return True
    files = source_files(DEFAULT_SOURCE)
    span = span.rstrip("/")
    if any(f == span or f.startswith(span + "/") for f in files):
        return True
    exported = TEAMTRACK / span
    return bool(span) and not _EXPORT_SKIP & set(Path(span).parts) and exported.exists()


def test_every_code_span_in_the_harness_docs_is_readable_by_the_bare_arm() -> None:
    readable = bare_arm_text()
    unknown: dict[str, list[str]] = {}
    for rel in source_files(DEFAULT_SOURCE):
        if not rel.endswith(".md"):
            continue
        for span in _CODE_SPAN.findall((DEFAULT_SOURCE / rel).read_text(encoding="utf-8")):
            if is_known_path(span) or normalise(span) in readable:
                continue
            unknown.setdefault(rel, []).append(span)
    assert unknown == {}
