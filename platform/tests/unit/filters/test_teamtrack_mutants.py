"""TeamTrack mutants: files load, sets are disjoint, and the visible suite kills every mutant.

The validation runs trusted TeamTrack code (a temporary copy of `teamtrack/`) in a LocalSandbox,
one mutant at a time per copy, several copies in parallel. Each mutant runs only the visible test
files that cover its module, and pytest stops at the first failure.
"""

from __future__ import annotations

import os
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from shipharness.filters.mutants import Mutant, load_mutants, run_mutant_detailed
from shipharness.layout import find_repo_root

from .helpers import PY, local_sandbox

TEAMTRACK = find_repo_root(Path(__file__)) / "platform" / "teamtrack"
MUTANTS_DIR = TEAMTRACK / "mutants"
V = "tests/visible/"

# Visible test files that exercise each module (run against every mutant of that module).
RELEVANT: dict[str, list[str]] = {
    "app.services.audit": [V + "test_idempotency_and_audit.py"],
    "app.services.auth": [V + "test_board.py", V + "test_auth.py", V + "test_roles.py"],
    "app.services.context": [
        V + "test_roles.py",
        V + "test_issues.py",
        V + "test_idempotency_and_audit.py",
    ],
    "app.services.errors": [V + "test_issues.py", V + "test_roles.py"],
    "app.services.idempotency": [V + "test_idempotency_and_audit.py"],
    "app.services.issues": [V + "test_issues.py", V + "test_tenant_isolation.py"],
    "app.services.legacy": [V + "test_legacy_and_schema.py"],
    "app.services.members": [V + "test_projects_users_members.py", V + "test_tenant_isolation.py"],
    "app.services.orgs": [V + "test_auth.py", V + "test_board.py"],
    "app.services.projects": [
        V + "test_projects_users_members.py",
        V + "test_tenant_isolation.py",
    ],
    "app.services.users": [
        V + "test_tenant_isolation.py",
        V + "test_projects_users_members.py",
        V + "test_idempotency_and_audit.py",
    ],
    "app.repositories.audit": [V + "test_idempotency_and_audit.py"],
    "app.repositories.common": [V + "test_lists.py"],
    "app.repositories.idempotency": [V + "test_idempotency_and_audit.py"],
    "app.repositories.issues": [
        V + "test_tenant_isolation.py",
        V + "test_issues.py",
        V + "test_legacy_and_schema.py",
    ],
    "app.repositories.members": [V + "test_projects_users_members.py"],
    "app.repositories.orgs": [V + "test_auth.py", V + "test_board.py"],
    "app.repositories.projects": [
        V + "test_tenant_isolation.py",
        V + "test_projects_users_members.py",
    ],
    "app.repositories.users": [V + "test_auth.py", V + "test_tenant_isolation.py"],
    "app.api.pagination": [V + "test_lists.py"],
}


def all_mutants() -> list[Mutant]:
    return [
        m for path in sorted(MUTANTS_DIR.glob("*.jsonl")) for m in load_mutants(path, TEAMTRACK)
    ]


def test_mutant_files_load_and_cover_twenty_modules() -> None:
    files = sorted(MUTANTS_DIR.glob("*.jsonl"))
    assert [f.stem for f in files] == sorted(RELEVANT)
    mutants = all_mutants()  # load_mutants checks every `original` against the source line
    per_target = Counter(m.target for m in mutants)
    assert len(per_target) == 20
    assert all(3 <= n <= 5 for n in per_target.values()), per_target
    assert len({m.id for m in mutants}) == len(mutants)
    for path in files:
        for m in load_mutants(path, TEAMTRACK):
            assert m.target == path.stem
            assert m.file == m.target.replace(".", "/") + ".py"
            assert m.rationale.strip()
            assert m.replacement != m.original


def test_each_module_has_both_sets_and_the_sets_are_disjoint() -> None:
    mutants = all_mutants()
    for target in RELEVANT:
        sets = {m.set for m in mutants if m.target == target}
        assert sets == {"filter", "referee"}, target
    filter_changes = {(m.file, m.line, m.replacement) for m in mutants if m.set == "filter"}
    referee_changes = {(m.file, m.line, m.replacement) for m in mutants if m.set == "referee"}
    assert not filter_changes & referee_changes


@pytest.fixture(scope="module")
def teamtrack_copy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("tt") / "teamtrack"
    shutil.copytree(
        TEAMTRACK,
        dest,
        ignore=shutil.ignore_patterns(
            "mutants", "hidden", "harness", "reference", "__pycache__", "*.db", ".pytest_cache"
        ),
    )
    return dest


def test_visible_suite_kills_every_mutant(teamtrack_copy: Path) -> None:
    mutants = all_mutants()

    def run(m: Mutant) -> tuple[Mutant, str, str]:
        result = run_mutant_detailed(
            m, RELEVANT[m.target], teamtrack_copy, local_sandbox(teamtrack_copy), 180, python=PY
        )
        return m, result.outcome, result.killed_by or result.detail

    workers = max(2, min(8, os.cpu_count() or 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(run, mutants))
    not_killed = [
        f"{m.id} ({m.set}): {outcome}: {detail}"
        for m, outcome, detail in outcomes
        if outcome != "killed"
    ]
    assert not not_killed, "\n".join(not_killed)
    counts = Counter(m.set for m in mutants)
    assert counts == {"filter": 41, "referee": 40}, counts
