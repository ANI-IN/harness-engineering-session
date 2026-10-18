"""Reference solution tests for R8."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from a4_verification.adapter import TeamTrackSoftDeleteAdapter
from a4_verification.r8_soft_delete import Probe, issue_param, judge
from sqlalchemy import create_engine, text

from shipharness.checks import CheckContext, get_check
from shipharness.checks.discovery import Endpoint

TEAMTRACK = Path(__file__).resolve().parents[4] / "platform" / "teamtrack"
MARKERS = {1: "[r8-deleted:1]", 11: "[r8-deleted:11]"}


def endpoint(method: str, path: str) -> Endpoint:
    params = [s[1:-1] for s in path.split("/") if s.startswith("{")]
    return Endpoint(
        method=method,
        path=path,
        operation_id=f"{method.lower()}_{path}",
        path_params=params,
        is_write=method != "GET",
        requires_auth=True,
        accepts_idempotency_key=False,
        has_body=method in ("POST", "PUT", "PATCH"),
    )


def probe(kind: str, method: str = "GET", path: str = "/x") -> Probe:
    return Probe(endpoint(method, path), kind, path)


def copy_app(tmp_path: Path, old: str = "", new: str = "") -> Path:
    build = tmp_path / "build"
    shutil.copytree(TEAMTRACK / "app", build / "app", ignore=shutil.ignore_patterns("__pycache__"))
    if old:
        repo = build / "app" / "repositories" / "issues.py"
        source = repo.read_text(encoding="utf-8")
        assert source.count(old) == 1
        repo.write_text(source.replace(old, new), encoding="utf-8")
    return build


def run(build: Path) -> set[tuple[str | None, str]]:
    result = get_check("r8_soft_delete").run(
        build, CheckContext(checkpoint="m1-base", feature_id="A4")
    )
    return {(f.endpoint, f.detail_key) for f in result.findings if f.counted}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/issues/{issue_id}", "issue_id"),
        ("/issues/{issue_id}/comments/{comment_id}", "issue_id"),
        ("/issues/{id}/history", "id"),
        ("/projects/{project_id}/issues/{issue_id}/peek", "issue_id"),
        ("/projects/{project_id}/issues", None),
        ("/projects/{id}", None),
        ("/issues/{label_id}", None),
        ("/v1/issues", None),
    ],
)
def test_issue_param(path: str, expected: str | None) -> None:
    assert issue_param(endpoint("GET", path)) == expected


def test_list_probe_fails_only_when_a_marker_is_in_a_success_body() -> None:
    assert judge(probe("deleted_list"), 200, '{"items": [{"id": 1}]}', MARKERS) is None
    assert judge(probe("deleted_list"), 404, "[r8-deleted:1]", MARKERS) is None
    finding = judge(probe("deleted_list"), 200, '{"title": "[r8-deleted:11]"}', MARKERS)
    assert finding is not None
    assert (finding.rule, finding.severity, finding.detail_key) == ("R8", "leak", "deleted_list")
    assert "[11]" in finding.detail


def test_path_probe_requires_404() -> None:
    assert judge(probe("deleted_path"), 404, "", MARKERS) is None
    deleted = judge(probe("deleted_path", "DELETE"), 204, "", MARKERS)
    assert deleted is not None and deleted.severity == "violation"
    shown = judge(probe("deleted_path"), 200, '{"title": "[r8-deleted:1]"}', MARKERS)
    assert shown is not None and shown.severity == "leak"
    assert judge(probe("deleted_path"), 422, "", MARKERS) is not None


def test_body_probe_fails_on_success_only() -> None:
    assert judge(probe("deleted_body", "POST"), 404, "", MARKERS) is None
    assert judge(probe("deleted_body", "POST"), 422, "", MARKERS) is None
    finding = judge(probe("deleted_body", "POST"), 201, "{}", MARKERS)
    assert finding is not None and finding.detail_key == "deleted_body"


def test_adapter_soft_deletes_the_first_issue_of_each_project() -> None:
    from shipharness.checks.probe import load_app

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.db"
        app = load_app(TEAMTRACK, db)
        ids = TeamTrackSoftDeleteAdapter().soft_delete(app, "acme")
        assert ids == [1, 11]
        engine = create_engine(f"sqlite:///{db.as_posix()}")
        with engine.connect() as con:
            rows = con.execute(
                text("SELECT id, title FROM issues WHERE deleted_at IS NOT NULL ORDER BY id")
            ).all()
        engine.dispose()
        app.state.session_factory.kw["bind"].dispose()
    assert [tuple(r) for r in rows] == [(1, "[r8-deleted:1]"), (11, "[r8-deleted:11]")]


def test_clean_teamtrack_has_only_the_legacy_finding(tmp_path: Path) -> None:
    assert run(copy_app(tmp_path)) == {("GET /v1/issues", "deleted_list")}


def test_list_without_the_deleted_filter_is_reported(tmp_path: Path) -> None:
    build = copy_app(
        tmp_path,
        "Issue.project_id == project_id, Issue.deleted_at.is_(None)",
        "Issue.project_id == project_id",
    )
    assert ("GET /projects/{project_id}/issues", "deleted_list") in run(build)
