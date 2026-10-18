"""diff_scope (S3 measures) and continuity (S2 measures)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from shipharness.checks import CheckContext, CheckResult, get_check
from shipharness.checks.builtin import load_builtin_checks
from shipharness.checks.diff_scope import changed_paths, matches
from tests.unit.checks import seeds

load_builtin_checks()

ALLOWED = {
    "build": ["app/api/issues.py", "app/services/", "migrations/versions/**"],
    "test": ["tests/**"],
}


def run(name: str, build: Path, allowed: dict[str, list[str]] | None = None, **params: object):  # type: ignore[no-untyped-def]
    ctx = CheckContext(
        checkpoint="m1-s3-start",
        feature_id="F3",
        phase_allowed_paths=ALLOWED if allowed is None else allowed,
        params=dict(params),
    )
    return get_check(name).run(build, ctx)


def keys(result: CheckResult) -> set[str]:
    return {f.detail_key for f in result.findings if f.counted}


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("app/services/issues.py", "app/services/", True),
        ("app/services/sub/x.py", "app/services/**", True),
        ("app/api/issues.py", "app/api/issues.py", True),
        ("app/api/middleware.py", "app/api/issues.py", False),
        ("tests/visible/test_x.py", "**/test_*.py", True),
        ("test_x.py", "**/test_*.py", True),
        ("docs/design-docs/a/b.md", "docs/design-docs/**", True),
        ("app/servicesx.py", "app/services", False),
    ],
)
def test_matches(path: str, pattern: str, expected: bool) -> None:
    assert matches(path, pattern) is expected


def test_changed_paths_from_a_unified_diff() -> None:
    diff = (
        "diff --git a/app/api/issues.py b/app/api/issues.py\n"
        "--- a/app/api/issues.py\n+++ b/app/api/issues.py\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/old.py b/old.py\ndeleted file mode 100644\n"
        "--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
    )
    assert changed_paths(diff) == ["app/api/issues.py", "old.py"]


def test_diff_scope_flags_out_of_scope_files_and_test_phase_source_edits(base_build: Path) -> None:
    result = run(
        "diff_scope",
        base_build,
        changed_files=["app/api/issues.py", "app/api/middleware.py", "tests/visible/test_new.py"],
        phase_files={"test": ["tests/visible/test_new.py", "app/services/issues.py"]},
    )
    assert keys(result) == {
        "out_of_scope:app/api/middleware.py",
        "test_phase_source_edit:app/services/issues.py",
    }
    assert result.total_probes == 3


def test_diff_scope_reads_the_diff_file(base_build: Path, tmp_path: Path) -> None:
    diff = tmp_path / "arm.patch"
    diff.write_text(
        "diff --git a/app/web/routes.py b/app/web/routes.py\n"
        "--- a/app/web/routes.py\n+++ b/app/web/routes.py\n@@ -1 +1 @@\n-a\n+b\n",
        encoding="utf-8",
    )
    result = run("diff_scope", base_build, diff_path=str(diff))
    assert keys(result) == {"out_of_scope:app/web/routes.py"}


def test_harness_artifacts_never_count_as_product_changes(base_build: Path) -> None:
    harness_files = [
        "AGENTS.md",
        "ARCHITECTURE.md",
        "docs/SECURITY.md",
        "docs/design-docs/index.md",
        "docs/references/fastapi-llms.txt",
        ".agents/skills/add-endpoint/SKILL.md",
        "init.sh",
        "progress.md",
        "session-handoff.md",
        "docs/exec-plans/active/F3.md",
        "feature_list.json",
        "feature_list.schema.json",
    ]
    result = run(
        "diff_scope",
        base_build,
        changed_files=[*harness_files, "app/api/issues.py"],
        phase_files={"test": ["progress.md", "docs/exec-plans/completed/F3.md"]},
    )
    assert result.passed is True, result.findings
    custom = run(
        "diff_scope",
        base_build,
        changed_files=["AGENTS.md", "notes/plan.txt"],
        harness_artifacts=["notes/**"],
    )
    assert keys(custom) == {"out_of_scope:AGENTS.md"}


def test_diff_scope_without_allowed_paths_is_an_error(base_build: Path) -> None:
    result = run("diff_scope", base_build, allowed={}, changed_files=["app/x.py"])
    assert [f.severity for f in result.findings] == ["error"]


# continuity -----------------------------------------------------------------------------------

SESSION_1 = (
    "diff --git a/app/services/comments.py b/app/services/comments.py\n"
    "--- /dev/null\n+++ b/app/services/comments.py\n@@ -0,0 +1,4 @@\n"
    "+def list_comments(session, actor, issue_id):\n"
    "+    rows = repo.list(session, actor.org_id, issue_id)\n"
    "+    return rows\n"
    "+\n"
)
SESSION_2_REDO = (
    "diff --git a/app/services/comments.py b/app/services/comments.py\n"
    "--- a/app/services/comments.py\n+++ b/app/services/comments.py\n@@ -1,3 +1,3 @@\n"
    "-def list_comments(session, actor, issue_id):\n"
    "-    rows = repo.list(session, actor.org_id, issue_id)\n"
    "+def list_comments(session, actor, issue_id, limit):\n"
    "+    rows = repo.list(session, actor.org_id, issue_id, limit)\n"
    "     return rows\n"
)
SESSION_2_ADD = (
    "diff --git a/app/services/comments.py b/app/services/comments.py\n"
    "--- a/app/services/comments.py\n+++ b/app/services/comments.py\n@@ -3,0 +4,1 @@\n"
    "+# more\n"
)


def patches(tmp_path: Path, *texts: str) -> list[str]:
    out = []
    for n, text in enumerate(texts, start=1):
        path = tmp_path / f"session{n}.patch"
        path.write_text(text, encoding="utf-8")
        out.append(str(path))
    return out


def test_continuity_base_with_additive_sessions_passes(base_build: Path, tmp_path: Path) -> None:
    result = run(
        "continuity", base_build, session_patches=patches(tmp_path, SESSION_1, SESSION_2_ADD)
    )
    assert result.passed is True, result.findings
    from shipharness.checks.scores import score_fields

    fields = score_fields([result])
    assert fields["continuity_failure"] is False
    assert fields["redone_lines_pct"] == 0.0


def test_continuity_catches_redone_work(base_build: Path, tmp_path: Path) -> None:
    result = run(
        "continuity", base_build, session_patches=patches(tmp_path, SESSION_1, SESSION_2_REDO)
    )
    assert keys(result) == {"redone_lines"}
    assert result.metrics["redone_lines_pct"] == pytest.approx(66.7, abs=0.1)


def test_continuity_catches_two_heads_and_duplicate_tables(
    make_build: Callable[[], Path],
) -> None:
    result = run("continuity", seeds.r7_two_heads(make_build()))
    assert {"r7:heads", "duplicate_table:comments"} <= keys(result)
    assert result.metrics["redone_lines_pct"] is None


def test_continuity_counts_only_the_scored_runs_session_stops(
    base_build: Path, tmp_path: Path
) -> None:
    """Both arms of an A/B write to one events.jsonl; S2 counts must not mix them."""
    import json

    log = tmp_path / "events.jsonl"
    events = [
        {"type": "session_stop", "run_id": "r-bare", "arm": "bare"},
        {"type": "session_stop", "run_id": "r-harness", "arm": "harness"},
        {"type": "session_stop", "run_id": "r-harness", "arm": "harness"},
        {"type": "turn", "run_id": "r-harness", "arm": "harness"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    harness = run("continuity", base_build, run_log=str(log), run_id="r-harness")
    bare = run("continuity", base_build, run_log=str(log), run_id="r-bare")
    assert (harness.metrics["sessions"], bare.metrics["sessions"]) == (2, 1)
