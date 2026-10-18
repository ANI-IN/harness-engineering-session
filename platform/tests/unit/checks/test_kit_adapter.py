"""The kit's adapter template (kit/templates/harness/shipharness_adapter.py) is TeamTrack's adapter.

It is a template a learner edits, so it must keep working unchanged on TeamTrack: the same answers
as the built-in TeamTrackAdapter, and the checks pass through it on the TeamTrack base.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from shipharness.ab.checkpoints import load_checkpoints
from shipharness.checks.adapter import TeamTrackAdapter
from shipharness.checks.runner import run_checks
from shipharness.kit.files import TEMPLATES

HARNESS_DIR = TEMPLATES / "harness"
SPEC = "shipharness_adapter:HouseRulesAdapter"


@pytest.fixture
def template(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.syspath_prepend(str(HARNESS_DIR))
    monkeypatch.delitem(sys.modules, "shipharness_adapter", raising=False)
    module = importlib.import_module("shipharness_adapter")
    monkeypatch.setitem(sys.modules, "shipharness_adapter", module)
    return module.HouseRulesAdapter()


def test_template_answers_like_the_teamtrack_adapter(template) -> None:  # type: ignore[no-untyped-def]
    built_in = TeamTrackAdapter()
    assert template.orgs() == built_in.orgs()
    for org in built_in.orgs():
        assert template.ids(org) == built_in.ids(org)
        for role in ("admin", "member", "viewer"):
            assert template.headers(org, role) == built_in.headers(org, role)
    for checkpoint in [*load_checkpoints(), "m1-base"]:
        assert template.exemptions(checkpoint) == built_in.exemptions(checkpoint), checkpoint
    assert template.layering_contract() == built_in.layering_contract()
    db = Path("/tmp/kit-adapter.db")
    assert template.migration_env(db) == built_in.migration_env(db)
    assert template.body_overrides() == built_in.body_overrides()
    assert template.bookkeeping_tables == built_in.bookkeeping_tables
    bodies = [
        [{"id": 21, "org_id": 2}],
        {"items": [{"project_id": 3, "user_id": 4}]},
        {"items": [{"id": 1, "org_id": 1}]},
        {"error": {"code": "not_found", "message": "x"}},
    ]
    for body in bodies:
        assert template.is_foreign(body, "globex") == built_in.is_foreign(body, "globex")


def test_template_counts_audit_rows_on_a_seeded_app(template, base_build: Path, tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = template.create_app(base_build, tmp_path / "kit.db")
    assert template.audit_count(app, "acme") == TeamTrackAdapter().audit_count(app, "acme")


def test_checks_pass_through_the_template_on_the_teamtrack_base(
    template,  # type: ignore[no-untyped-def]
    base_build: Path,
) -> None:
    results, crashed = run_checks(
        base_build,
        ["r2_roles", "r5_audit", "r6_layering"],
        checkpoint="m1-base",
        feature_id="-",
        seed=0,
        params={"adapter": SPEC},
    )
    assert not crashed
    assert {r.check: r.passed for r in results} == {
        "r2_roles": True,
        "r5_audit": True,
        "r6_layering": True,
    }
