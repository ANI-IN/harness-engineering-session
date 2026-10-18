"""Tenant app adapter (contract I-2): the app-specific facts the generic checks need.

Checks are generic for FastAPI services. Everything that depends on one application (how to build
it, how to authenticate as a role, which ids belong to which org) goes through an adapter. The
TeamTrack adapter is built in; `shipharness check --adapter module:attr` loads another.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from shipharness.checks.probe import load_app


@runtime_checkable
class TenantAppAdapter(Protocol):
    """What a check may ask about an application. Org names are opaque strings."""

    def create_app(self, build_dir: Path, db_path: Path) -> Any:
        """Import the build and return a seeded ASGI app on a fresh database at `db_path`."""
        ...

    def headers(self, org: str, role: str) -> dict[str, str]:
        """Request headers that authenticate as the seeded user with `role` in `org`."""
        ...

    def orgs(self) -> tuple[str, str]:
        """(home, other): probes run as `home` and point at `other`'s data."""
        ...

    def ids(self, org: str) -> dict[str, int]:
        """Values for path parameters and body ids, by name (`issue_id`, `project_id`, ...)."""
        ...

    def audit_count(self, app: Any, org: str) -> int:
        """Number of audit rows recorded for `org`."""
        ...

    def is_foreign(self, body: Any, org: str) -> bool:
        """True if a response body contains data owned by `org`."""
        ...

    def exemptions(self, checkpoint: str) -> dict[str, list[str]]:
        """Default per-rule exemptions at a checkpoint, e.g. {"R4": ["POST /x"]}."""
        ...

    def migration_env(self, db_path: Path) -> dict[str, str]:
        """Environment variables that point the build's Alembic setup at `db_path`."""
        ...

    def layering_contract(self) -> str:
        """Trusted import-linter configuration for R6 (never read from the build)."""
        ...

    def board_login(self, org: str, role: str) -> tuple[str, dict[str, str]]:
        """(path, form fields) that sign a browser in to the board."""
        ...

    def board_path(self, org: str) -> str:
        """Path of the board page for `org`'s first project (redirects are followed)."""
        ...

    def body_overrides(self) -> dict[str, dict[str, Any]]:
        """Body fields by endpoint label that generated data cannot get right (business rules)."""
        ...

    bookkeeping_tables: frozenset[str]  # tables R4 ignores when counting new records


@dataclass(frozen=True)
class _Org:
    org_id: int
    admin: int
    member: int
    viewer: int
    projects: tuple[int, ...]
    issues: tuple[int, ...]
    comments: tuple[int, ...] = ()  # seeded by F2: two per org, on the org's first issue
    labels: tuple[int, ...] = ()  # seeded by F7: three per org

    @property
    def users(self) -> tuple[int, ...]:
        return (self.admin, self.member, self.viewer)


# Mirrors teamtrack/app/seed.py (stable ids by design; a unit test keeps them in sync). The adapter
# never imports the build to learn them: the build is untrusted.
_TEAMTRACK_ORGS = {
    "acme": _Org(1, 1, 2, 3, (1, 2), tuple(range(1, 21)), (1, 2), (1, 2, 3)),
    "globex": _Org(2, 4, 5, 6, (3, 4), tuple(range(21, 41)), (3, 4), (4, 5, 6)),
}
# Checkpoints without F3 (idempotent issue create). teamtrack/reference/checkpoints.toml lists
# each checkpoint's tasks; a unit test keeps this set in sync with it.
_BEFORE_F3 = frozenset(
    {"m1-base", "m1-s1-start", "m1-s2-start", "m1-s3-start", "m1-alt-a", "m1-alt-b"}
)
_R6_CONTRACT = """\
[importlinter]
root_package = app

[importlinter:contract:r6]
name = R6: app.api and app.web never import app.db
type = forbidden
source_modules =
    app.api
    app.web
forbidden_modules =
    app.db
allow_indirect_imports = True
"""
_USER_FIELDS = ("user_id", "assignee_id", "created_by", "actor_id")


class TeamTrackAdapter:
    """Adapter for the bundled TeamTrack demo app (orgs `acme` and `globex`)."""

    bookkeeping_tables = frozenset({"audit_log", "idempotency_keys", "alembic_version"})

    def create_app(self, build_dir: Path, db_path: Path) -> Any:
        return load_app(build_dir, db_path)

    def headers(self, org: str, role: str) -> dict[str, str]:
        user_id = getattr(_TEAMTRACK_ORGS[org], role)
        return {"Authorization": f"Bearer tt-{user_id}"}

    def orgs(self) -> tuple[str, str]:
        return ("acme", "globex")

    def ids(self, org: str) -> dict[str, int]:
        o = _TEAMTRACK_ORGS[org]
        return {
            "issue_id": o.issues[0],
            "project_id": o.projects[0],
            # The viewer is not a project member at seed time, so adding then removing works.
            "user_id": o.viewer,
            "assignee_id": o.member,
            "org_id": o.org_id,
            # Path parameters added by features (F2 comments, F7 labels); unused without them.
            "comment_id": o.comments[0],
            "label_id": o.labels[0],
        }

    def audit_count(self, app: Any, org: str) -> int:
        from sqlalchemy import text

        with app.state.session_factory() as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM audit_log WHERE org_id = :org"),
                {"org": _TEAMTRACK_ORGS[org].org_id},
            ).scalar_one()
        return int(count)

    def is_foreign(self, body: Any, org: str) -> bool:
        o = _TEAMTRACK_ORGS[org]
        for item in _dicts(body):
            if item.get("org_id") == o.org_id:
                return True
            if item.get("project_id") in o.projects or item.get("issue_id") in o.issues:
                return True
            if any(item.get(name) in o.users for name in _USER_FIELDS):
                return True
        return False

    def exemptions(self, checkpoint: str) -> dict[str, list[str]]:
        # The legacy /v1/issues envelope is documented legacy (HANDBOOK "Legacy /v1 API"). Its R1
        # leak is NOT exempt: it is part of every baseline and must stay visible.
        exempt: dict[str, list[str]] = {"R3": ["GET /v1/issues"]}
        if checkpoint in _BEFORE_F3:
            exempt["R4"] = ["POST /projects/{project_id}/issues"]
        return exempt

    def migration_env(self, db_path: Path) -> dict[str, str]:
        return {"TEAMTRACK_DATABASE_URL": f"sqlite:///{Path(db_path).as_posix()}"}

    def layering_contract(self) -> str:
        return _R6_CONTRACT

    def board_login(self, org: str, role: str) -> tuple[str, dict[str, str]]:
        return "/board/login", {"email": f"{role}@{org}.test"}

    def board_path(self, org: str) -> str:
        return "/board"

    def body_overrides(self) -> dict[str, dict[str, Any]]:
        # Seeded issues start "open"; the first enum value ("open") is not an allowed transition.
        return {"POST /issues/{issue_id}/transition": {"status": "in_progress"}}


def _dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _dicts(child)


def load_adapter(spec: str | None) -> TenantAppAdapter:
    """`module:attr` names a class (instantiated with no arguments) or an adapter instance."""
    if not spec:
        return TeamTrackAdapter()
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"adapter must be given as module:attr, got {spec!r}")
    target = getattr(importlib.import_module(module_name), attr)
    adapter = target() if isinstance(target, type) else target
    return adapter  # type: ignore[no-any-return]
