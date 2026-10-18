from __future__ import annotations

import re
from pathlib import Path

import pytest

from shipharness.ab.workspace import (
    CheckpointNotFound,
    WorkspaceInsideCheckout,
    create_arm_workspace,
    export_checkpoint,
    export_hidden_tests,
    new_ab_id,
    new_run_id,
)
from shipharness.runner import git as run_git

from .conftest import git, write


def files(root: Path) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    )


def test_ids_follow_the_contract_format() -> None:
    assert re.fullmatch(r"ab-\d{8}-\d{6}-[0-9a-f]{6}", new_ab_id())
    assert re.fullmatch(r"r-\d{8}-\d{6}-[0-9a-f]{6}", new_run_id())


def test_export_filters_referee_only_and_generated_files(course_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "out"
    export_checkpoint(course_repo, "m1-s1-start", dest)
    assert files(dest) == [
        "app/api/issues.py",
        "app/main.py",
        "docs/HANDBOOK.md",
        "tests/visible/test_app.py",
    ]


def test_export_uses_the_tagged_commit_not_the_working_tree(
    course_repo: Path, tmp_path: Path
) -> None:
    write(course_repo / "teamtrack" / "app" / "main.py", "CHANGED AFTER TAG\n")
    dest = tmp_path / "out"
    export_checkpoint(course_repo, "m1-s1-start", dest)
    assert "CHANGED" not in (dest / "app" / "main.py").read_text(encoding="utf-8")


def test_unknown_checkpoint_is_an_error(course_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(CheckpointNotFound, match="m9-nothing"):
        export_checkpoint(course_repo, "m9-nothing", tmp_path / "out")


def test_working_tree_source_when_no_ref(course_repo: Path, tmp_path: Path) -> None:
    write(course_repo / "teamtrack" / "app" / "new.py", "N = 1\n")
    dest = tmp_path / "out"
    export_checkpoint(course_repo, None, dest)
    assert "app/new.py" in files(dest)
    assert not any(f.startswith(("harness/", "tests/hidden/", "reference/")) for f in files(dest))


def test_working_tree_export_skips_tool_caches(course_repo: Path, tmp_path: Path) -> None:
    tt = course_repo / "teamtrack"
    for cache in (
        ".import_linter_cache/abc.json",
        ".pytest_cache/v/cache/lastfailed",
        ".ruff_cache/0.9/123",
        ".mypy_cache/3.12/app.json",
        ".hypothesis/examples/1",
        "app/.pytest_cache/v/x",  # nested caches too
    ):
        write(tt / cache, "cache\n")
    tree, tag = tmp_path / "tree", tmp_path / "tag"
    export_checkpoint(course_repo, None, tree)
    export_checkpoint(course_repo, "m1-s1-start", tag)
    assert files(tree) == files(tag)  # the materialized tree matches the tag tree


def test_arm_workspace_is_a_fresh_repo_with_one_commit(course_repo: Path, tmp_path: Path) -> None:
    ws = create_arm_workspace("ab-1", "bare", course_repo, "m1-s1-start", base=tmp_path / "wsroot")
    assert ws == tmp_path / "wsroot" / "ab-1" / "bare" / "ws"
    assert (ws / ".git").is_dir()  # a real repository, not a worktree (.git file)
    assert git(ws, "rev-list", "--all", "--count") == "1"
    assert git(ws, "remote") == ""
    assert git(ws, "tag") == ""
    assert git(ws, "status", "--porcelain") == ""
    assert "tests/hidden" not in git(ws, "log", "--all", "--name-only", "--format=")


def test_both_arms_start_from_the_same_commit(course_repo: Path, tmp_path: Path) -> None:
    base = tmp_path / "wsroot"
    bare = create_arm_workspace("ab-2", "bare", course_repo, "m1-s1-start", base=base)
    harness = create_arm_workspace("ab-2", "harness", course_repo, "m1-s1-start", base=base)
    assert run_git.head_sha(bare) == run_git.head_sha(harness) != ""
    assert files(bare) == files(harness)


def test_workspace_inside_the_course_checkout_is_refused(course_repo: Path) -> None:
    with pytest.raises(WorkspaceInsideCheckout):
        create_arm_workspace("ab-3", "bare", course_repo, "m1-s1-start", base=course_repo / "ws")


def test_default_base_is_outside_the_checkout_in_system_temp(course_repo: Path) -> None:
    import tempfile

    from shipharness.ab.workspace import workspace_base

    base = workspace_base()
    assert base == Path(tempfile.gettempdir()) / "shipharness-ws"


def test_existing_workspace_is_never_reused(course_repo: Path, tmp_path: Path) -> None:
    base = tmp_path / "wsroot"
    create_arm_workspace("ab-4", "bare", course_repo, "m1-s1-start", base=base)
    with pytest.raises(FileExistsError):
        create_arm_workspace("ab-4", "bare", course_repo, "m1-s1-start", base=base)


def test_hidden_tests_export_is_separate(course_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "hidden"
    export_hidden_tests(course_repo, "m1-s1-start", dest)
    assert files(dest) == ["f1/test_secret.py"]


def test_a_workspace_repo_never_starts_background_git_maintenance(tmp_path: Path) -> None:
    # CI 2026-10-17: auto maintenance left objects/maintenance.lock behind while a test removed the
    # workspace (FileNotFoundError in teardown). Every later commit in the workspace inherits this.
    import subprocess

    from shipharness.ab.workspace import init_repo

    write(tmp_path / "ws" / "a.txt", "a")
    init_repo(tmp_path / "ws", "start")

    def config(key: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(tmp_path / "ws"), "config", "--get", key],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.stdout.strip()

    assert config("maintenance.auto") == "false"
    assert config("gc.auto") == "0"
