"""Export inspection (1): an arm workspace holds the checkpoint only.

A miniature course repository carries everything an arm must never reach: reference solutions,
hidden tests, referee mutants, harness instruction sources, course files outside `teamtrack/`, a
second branch with a secret file, tags, and a commit made after the checkpoint. The workspace is
created through the real `create_arm_workspace` and inspected both as a file tree and as a git
repository (every object in its object store, not only the reachable ones).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shipharness.ab.workspace import create_arm_workspace

from .conftest import ENV, git, write

FORBIDDEN_PREFIXES = ("reference/", "tests/hidden/", "mutants/", "harness/")


@pytest.fixture
def course(tmp_path: Path) -> dict[str, object]:
    repo = tmp_path / "course"
    tt = repo / "teamtrack"
    write(tt / "app" / "main.py", "def create_app():\n    return 'app'\n")
    write(tt / "app" / "api" / "issues.py", "def list_issues():\n    return []\n")
    write(tt / "app" / "reference" / "nested.py", "NESTED_REFERENCE = 'reference-nested-7f3a'\n")
    write(tt / "docs" / "HANDBOOK.md", "# Handbook\nR1 tenant isolation\n")
    write(tt / "tests" / "visible" / "test_app.py", "def test_app():\n    assert True\n")
    write(
        tt / "tests" / "hidden" / "f1" / "test_secret.py",
        "def test_hidden_only():\n    assert 'hidden-5c1e'\n",
    )
    write(tt / "mutants" / "app.services.issues.jsonl", '{"id": "mutant-91d2"}\n')
    write(tt / "reference" / "f1" / "issues.py", "SOLUTION = 'reference-solution-b8e4'\n")
    write(tt / "harness" / "instructions" / "AGENTS.md", "# Harness map 0c6f\n")
    write(tt / "harness" / "skills" / "tenant.md", "# Harness skill 3a9b\n")
    write(tt / "teamtrack.db", "sqlite-6d2e")
    write(repo / "README.md", "course readme 4b7c\n")
    write(repo / "skills" / "course-skill.md", "# Course skill 8e1d\n")
    write(repo / "instructor" / "notes.md", "instructor notes 2f5a\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "course checkpoint")
    git(repo, "tag", "m1-s1-start")
    git(repo, "tag", "-a", "annotated-tag", "-m", "annotated")

    git(repo, "checkout", "-q", "-b", "solutions")
    write(tt / "app" / "secret.py", "SECRET = 'solution-branch-only-e3b0'\n")
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "solutions branch")
    git(repo, "tag", "solutions-tag")
    secret_blob = git(repo, "rev-parse", "solutions:teamtrack/app/secret.py")
    solutions_commit = git(repo, "rev-parse", "solutions")

    git(repo, "checkout", "-q", "main")
    write(tt / "app" / "later.py", "LATER = 'after-the-checkpoint-a1c9'\n")
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "after the checkpoint")
    later_commit = git(repo, "rev-parse", "main")

    forbidden_blobs = {
        path: git(repo, "rev-parse", f"m1-s1-start:{path}")
        for path in (
            "teamtrack/app/reference/nested.py",
            "teamtrack/tests/hidden/f1/test_secret.py",
            "teamtrack/mutants/app.services.issues.jsonl",
            "teamtrack/reference/f1/issues.py",
            "teamtrack/harness/instructions/AGENTS.md",
            "teamtrack/harness/skills/tenant.md",
            "teamtrack/teamtrack.db",
            "README.md",
            "skills/course-skill.md",
            "instructor/notes.md",
        )
    }
    forbidden_blobs["secret"] = secret_blob
    forbidden_blobs["later"] = git(repo, "rev-parse", "main:teamtrack/app/later.py")
    return {
        "repo": repo,
        "checkpoint_commit": git(repo, "rev-parse", "m1-s1-start^{commit}"),
        "forbidden_objects": {
            **forbidden_blobs,
            "solutions_commit": solutions_commit,
            "later_commit": later_commit,
            "annotated_tag": git(repo, "rev-parse", "annotated-tag"),
        },
    }


def ws_git(ws: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ws, capture_output=True, text=True, env=ENV, check=check
    )


def lines(ws: Path, *args: str) -> list[str]:
    return [line for line in ws_git(ws, *args).stdout.splitlines() if line.strip()]


@pytest.fixture
def workspace(course: dict[str, object], tmp_path: Path) -> Path:
    repo = course["repo"]
    assert isinstance(repo, Path)
    return create_arm_workspace(
        "ab-inspect", "harness", repo, "m1-s1-start", base=tmp_path / "ws", course_root=repo
    )


def test_workspace_tree_holds_only_checkpoint_product_files(workspace: Path) -> None:
    tree = sorted(
        p.relative_to(workspace).as_posix()
        for p in workspace.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(workspace).parts
    )
    assert tree == [
        "app/api/issues.py",
        "app/main.py",
        "docs/HANDBOOK.md",
        "tests/visible/test_app.py",
    ]
    for rel in tree:
        assert not rel.startswith(FORBIDDEN_PREFIXES), rel
        assert "/reference/" not in f"/{rel}" and not rel.endswith(".db"), rel
    text = "".join(
        (workspace / rel).read_text(encoding="utf-8") for rel in tree
    )  # nothing from the forbidden files leaked into a kept one
    for marker in ("reference-", "hidden-5c1e", "mutant-91d2", "Harness map", "e3b0", "a1c9"):
        assert marker not in text


def test_workspace_git_shows_only_the_one_checkpoint_commit(workspace: Path) -> None:
    head = ws_git(workspace, "rev-parse", "HEAD").stdout.strip()
    assert lines(workspace, "log", "--all", "--format=%H") == [head]
    assert [b.strip("* ").strip() for b in lines(workspace, "branch", "-a")] == ["main"]
    assert lines(workspace, "tag") == []
    assert lines(workspace, "remote") == []
    assert lines(workspace, "stash", "list") == []
    git_dir = workspace / ".git"
    assert git_dir.is_dir()  # a repository of its own, never a worktree (.git file)
    assert not (git_dir / "commondir").exists()
    assert not (git_dir / "objects" / "info" / "alternates").exists()


def test_workspace_object_store_holds_only_checkpoint_objects(
    workspace: Path, course: dict[str, object]
) -> None:
    head = ws_git(workspace, "rev-parse", "HEAD").stdout.strip()
    tree_objects = {line.split()[2] for line in lines(workspace, "ls-tree", "-r", "-t", "HEAD")}
    root_tree = ws_git(workspace, "rev-parse", "HEAD^{tree}").stdout.strip()
    expected = {head, root_tree, *tree_objects}
    reachable = {line.split()[0] for line in lines(workspace, "rev-list", "--all", "--objects")}
    assert reachable == expected
    stored = set(lines(workspace, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)"))
    assert stored == expected  # nothing unreachable is stored either
    assert head != course["checkpoint_commit"]  # a fresh commit, not the course history


def test_course_only_objects_are_absent_from_the_workspace(
    workspace: Path, course: dict[str, object]
) -> None:
    forbidden = course["forbidden_objects"]
    assert isinstance(forbidden, dict)
    for name, sha in forbidden.items():
        probe = ws_git(workspace, "cat-file", "-e", sha, check=False)
        assert probe.returncode != 0, f"{name} ({sha}) is reachable in the arm workspace"
