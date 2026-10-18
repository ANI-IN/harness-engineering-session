"""Demo data: two orgs (Acme, Globex) with stable IDs so cross-tenant probes are reproducible."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import issues as issues_repo
from app.repositories import members as members_repo
from app.repositories import orgs as orgs_repo
from app.repositories import projects as projects_repo
from app.repositories import users as users_repo
from app.repositories import watchers as watchers_repo


@dataclass(frozen=True)
class SeedOrg:
    org_id: int
    slug: str
    admin: int
    member: int
    viewer: int
    projects: tuple[int, ...]
    issues: tuple[int, ...]  # all issues in the org; the first ten belong to projects[0]


ACME = SeedOrg(
    org_id=1, slug="acme", admin=1, member=2, viewer=3, projects=(1, 2), issues=tuple(range(1, 21))
)
GLOBEX = SeedOrg(
    org_id=2,
    slug="globex",
    admin=4,
    member=5,
    viewer=6,
    projects=(3, 4),
    issues=tuple(range(21, 41)),
)

_ORGS = [
    (ACME, "Acme", [("Website", "WEB"), ("Mobile", "MOB")]),
    (GLOBEX, "Globex", [("Billing", "BIL"), ("Platform", "PLT")]),
]
_TITLES = [
    "Login page times out",
    "Export to CSV drops the last row",
    "Typo on pricing page",
    "Search ignores accents",
    "Dark mode contrast too low",
    "Password reset email delayed",
    "Avatar upload fails for PNG",
    "Pagination skips an item",
    "Slow dashboard load",
    "Broken link in footer",
]
_PRIORITIES = ["low", "medium", "high"]
# Each org's member watches the org's first two issues: watcher ids 1-2 (Acme), 3-4 (Globex).
SEED_WATCHERS = {ACME.slug: (1, 2), GLOBEX.slug: (3, 4)}


def _seed_watchers(session: Session) -> None:
    for spec, _name, _projects in _ORGS:
        for issue_id, watcher_id in zip(spec.issues[:2], SEED_WATCHERS[spec.slug], strict=True):
            watcher = watchers_repo.add(session, spec.org_id, issue_id, spec.member)
            assert watcher.id == watcher_id


def seed(session: Session) -> None:
    """Insert the demo data into an empty database. IDs must match ACME and GLOBEX."""
    if orgs_repo.count(session) > 0:
        return
    created_orgs = [orgs_repo.add(session, name, spec.slug) for spec, name, _ in _ORGS]
    for (spec, _name, _projects), org in zip(_ORGS, created_orgs, strict=True):
        assert org.id == spec.org_id, "seed must run on an empty database"
        for role in ("admin", "member", "viewer"):
            user = users_repo.add(
                session,
                org.id,
                f"{role}@{spec.slug}.test",
                f"{spec.slug.title()} {role.title()}",
                role,
            )
            assert user.id == getattr(spec, role)
    for spec, _name, project_specs in _ORGS:
        for project_spec, project_id in zip(project_specs, spec.projects, strict=True):
            project = projects_repo.add(session, spec.org_id, *project_spec)
            assert project.id == project_id
            members_repo.add(session, project.id, spec.admin)
            members_repo.add(session, project.id, spec.member)
    issue_ids = iter(ACME.issues + GLOBEX.issues)
    for spec, _name, _projects in _ORGS:
        for project_id in spec.projects:
            for n, title in enumerate(_TITLES):
                issue = issues_repo.add(
                    session,
                    spec.org_id,
                    project_id,
                    title,
                    f"Reported in project {project_id}.",
                    _PRIORITIES[n % 3],
                    spec.member if n % 2 == 0 else None,
                    spec.admin,
                )
                assert issue.id == next(issue_ids)
    _seed_watchers(session)
    session.commit()
