"""House-rule adapter for `shipharness check`: the facts about your app that the checks need.

Every value in this file is TeamTrack's, copied from `TeamTrackAdapter` in
`src/shipharness/checks/adapter.py` of the shipharness repository, so the file works unchanged on
TeamTrack. Replace each value marked REPLACE with your app's, and delete the methods of the rules
you do not run (docs/house-rules.md lists which rule calls which method).

Run it from your repository root; PYTHONPATH makes this file importable:

    PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . \
        --adapter shipharness_adapter:HouseRulesAdapter --rules R1,R2,R3,R4,R5,R6,R7

The checks import and run your app's code in this process: run them only on code you trust.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Org:
    org_id: int
    admin: int
    member: int
    viewer: int
    projects: tuple[int, ...]
    issues: tuple[int, ...]
    comments: tuple[int, ...] = ()
    labels: tuple[int, ...] = ()

    @property
    def users(self) -> tuple[int, ...]:
        return (self.admin, self.member, self.viewer)


# REPLACE: two tenants of your seeded demo data, with the ids of their rows.
# Probes run as the first tenant and point at the second's data. TeamTrack seeds the orgs acme
# and globex (teamtrack/app/seed.py); the adapter never imports the app to learn them.
ORGS = {
    "acme": Org(1, 1, 2, 3, (1, 2), tuple(range(1, 21)), (1, 2), (1, 2, 3)),
    "globex": Org(2, 4, 5, 6, (3, 4), tuple(range(21, 41)), (3, 4), (4, 5, 6)),
}
# REPLACE: checkpoints (the --checkpoint value, default m1-base) with extra exemptions.
# TeamTrack exempts issue creation from R4 until feature F3 exists. Most repositories need
# none: delete this set and return the same exemptions for every checkpoint.
BEFORE_F3 = frozenset(
    {"m1-base", "m1-s1-start", "m1-s2-start", "m1-s3-start", "m1-alt-a", "m1-alt-b"}
)
# REPLACE: your layering rule as an import-linter contract, for R6.
# It lives here, not in your repository's own config, so a change under review cannot weaken it.
LAYERING_CONTRACT = """\
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
# REPLACE: response fields that hold a user id, so R1 can spot another tenant's users in a body.
USER_FIELDS = ("user_id", "assignee_id", "created_by", "actor_id")


class HouseRulesAdapter:
    """Adapter for TeamTrack (orgs `acme` and `globex`)."""

    # REPLACE: tables R4 ignores when it counts new rows after a repeated create.
    bookkeeping_tables = frozenset({"audit_log", "idempotency_keys", "alembic_version"})

    def create_app(self, build_dir: Path, db_path: Path) -> Any:
        """A seeded ASGI app on a fresh SQLite file at `db_path` (R1-R5)."""
        # REPLACE: import your app factory from build_dir; give it db_path and demo data.
        # TeamTrack: app.main.create_app(TeamTrackSettings(database_url, create_schema, seed)).
        root = str(Path(build_dir).resolve())
        for name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
            del sys.modules[name]
        sys.path.insert(0, root)
        try:
            main = importlib.import_module("app.main")
            settings_module = importlib.import_module("app.settings")
            settings = settings_module.TeamTrackSettings(
                database_url=f"sqlite:///{Path(db_path).as_posix()}",
                create_schema=True,
                seed=True,
            )
            return main.create_app(settings)
        finally:
            sys.path.remove(root)

    def headers(self, org: str, role: str) -> dict[str, str]:
        """Headers that authenticate as the seeded user with `role` in `org` (R1-R5)."""
        # REPLACE: how a test client signs in as a role. TeamTrack's demo token is tt-<user id>.
        user_id = getattr(ORGS[org], role)
        return {"Authorization": f"Bearer tt-{user_id}"}

    def orgs(self) -> tuple[str, str]:
        """(home, other): probes run as `home` and point at `other`'s data."""
        return ("acme", "globex")

    def ids(self, org: str) -> dict[str, int]:
        """Values for path parameters and body ids, by parameter name."""
        # REPLACE: one seeded id per path parameter name your OpenAPI schema uses.
        o = ORGS[org]
        return {
            "issue_id": o.issues[0],
            "project_id": o.projects[0],
            "user_id": o.viewer,
            "assignee_id": o.member,
            "org_id": o.org_id,
            "comment_id": o.comments[0],
            "label_id": o.labels[0],
        }

    def audit_count(self, app: Any, org: str) -> int:
        """Audit rows recorded for `org` (R5)."""
        # REPLACE: count your audit rows for one tenant, or delete this method if you skip R5.
        from sqlalchemy import text

        with app.state.session_factory() as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM audit_log WHERE org_id = :org"),
                {"org": ORGS[org].org_id},
            ).scalar_one()
        return int(count)

    def is_foreign(self, body: Any, org: str) -> bool:
        """True if a response body contains data owned by `org` (R1)."""
        # REPLACE: the fields that tie a row to a tenant in your responses.
        o = ORGS[org]
        for item in _dicts(body):
            if item.get("org_id") == o.org_id:
                return True
            if item.get("project_id") in o.projects or item.get("issue_id") in o.issues:
                return True
            if any(item.get(name) in o.users for name in USER_FIELDS):
                return True
        return False

    def exemptions(self, checkpoint: str) -> dict[str, list[str]]:
        """Findings that are reported as info and do not count, per rule: {"R3": ["GET /x"]}."""
        # REPLACE: documented exceptions, each with a reason written in your docs.
        # TeamTrack exempts the legacy GET /v1/issues envelope from R3 and keeps its R1 leak
        # visible on purpose, so the baseline shows it.
        exempt: dict[str, list[str]] = {"R3": ["GET /v1/issues"]}
        if checkpoint in BEFORE_F3:
            exempt["R4"] = ["POST /projects/{project_id}/issues"]
        return exempt

    def migration_env(self, db_path: Path) -> dict[str, str]:
        """Environment that points your Alembic setup at `db_path` (R7)."""
        # REPLACE: the variable your migrations read for the database URL.
        return {"TEAMTRACK_DATABASE_URL": f"sqlite:///{Path(db_path).as_posix()}"}

    def layering_contract(self) -> str:
        """The import-linter configuration R6 runs."""
        return LAYERING_CONTRACT

    def body_overrides(self) -> dict[str, dict[str, Any]]:
        """Body fields by endpoint that generated data cannot get right (business rules)."""
        # REPLACE: request bodies that need a specific value to succeed.
        # TeamTrack: a seeded issue starts open, and open to open is not an allowed transition.
        return {"POST /issues/{issue_id}/transition": {"status": "in_progress"}}


def _dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _dicts(child)
