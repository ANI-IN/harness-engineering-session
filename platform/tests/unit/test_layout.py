"""shipharness.layout: the repository root by its marker, and TeamTrack's directory per commit.

Recorded A/B results pin checkpoint commits made before the course-first layout (TeamTrack at
`teamtrack/`); every reader of a checkpoint tree must still find TeamTrack there.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from shipharness import layout
from shipharness.ab.workspace import export_checkpoint, export_hidden_tests
from shipharness.config import prices


def _git(cwd: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t.invalid",
    )
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, env=env, check=True)
    return done.stdout.decode().strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_root_is_found_by_its_marker_not_by_a_fixed_depth(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    deep = tmp_path / "platform" / "src" / "pkg" / "sub"
    deep.mkdir(parents=True)
    assert layout.find_repo_root(deep) == tmp_path.resolve()
    assert layout.find_repo_root(deep / "module.py") == tmp_path.resolve()
    with pytest.raises(layout.RepoRootNotFound):
        layout.find_repo_root(tmp_path.parent, marker="no-such-marker.toml")


def test_the_package_finds_this_checkout_root() -> None:
    root = Path(__file__).resolve().parents[3]
    assert (root / "pyproject.toml").is_file()
    assert root == layout.REPO_ROOT
    assert root == prices.REPO_ROOT
    assert root / "platform" / "config" / "prices.toml" == prices.DEFAULT_PRICES_FILE
    assert prices.DEFAULT_PRICES_FILE.is_file()
    assert (root / layout.APP_DIR / "app").is_dir()


def test_logical_data_paths_map_to_the_current_layout() -> None:
    assert layout.logical_path("teamtrack/mutants/x.jsonl") == "platform/teamtrack/mutants/x.jsonl"
    assert (
        layout.logical_path("teamtrack/mutants/x.jsonl", "teamtrack") == "teamtrack/mutants/x.jsonl"
    )
    assert (
        layout.logical_path("datasets/mutants/b/x.jsonl") == "platform/datasets/mutants/b/x.jsonl"
    )
    assert layout.logical_path("platform/datasets/a.jsonl") == "platform/datasets/a.jsonl"
    assert layout.logical_path("app/main.py") == "app/main.py"


@pytest.fixture
def two_layouts(tmp_path: Path) -> tuple[Path, str, str]:
    """A repository with one commit in the old layout and one in the course-first layout."""
    repo = tmp_path / "repo"
    _write(repo, "teamtrack/app/main.py", "OLD = True\n")
    _write(repo, "teamtrack/tests/hidden/f1/test_h.py", "def test_h():\n    pass\n")
    _write(repo, "teamtrack/harness/instructions/AGENTS.md", "# map\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "old layout")
    old = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "teamtrack", "tt")
    (repo / "platform").mkdir()
    _git(repo, "mv", "tt", "platform/teamtrack")
    _write(repo, "platform/teamtrack/app/main.py", "NEW = True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "course-first layout")
    return repo, old, _git(repo, "rev-parse", "HEAD")


def test_app_dir_is_resolved_per_commit(two_layouts: tuple[Path, str, str]) -> None:
    repo, old, new = two_layouts
    assert layout.app_dir_at(repo, old) == "teamtrack"
    assert layout.app_dir_at(repo, new) == "platform/teamtrack"
    assert layout.app_dir_at(repo) == "platform/teamtrack"  # the working tree


def test_an_old_layout_checkpoint_still_exports(
    two_layouts: tuple[Path, str, str], tmp_path: Path
) -> None:
    repo, old, new = two_layouts
    ws = export_checkpoint(repo, old, tmp_path / "old")
    assert (ws / "app" / "main.py").read_text(encoding="utf-8") == "OLD = True\n"
    assert not (ws / "harness").exists()  # still filtered
    hidden = export_hidden_tests(repo, old, tmp_path / "old-hidden")
    assert (hidden / "f1" / "test_h.py").is_file()
    ws_new = export_checkpoint(repo, new, tmp_path / "new")
    assert (ws_new / "app" / "main.py").read_text(encoding="utf-8") == "NEW = True\n"


def test_resolve_prefers_the_current_layout_and_falls_back(tmp_path: Path) -> None:
    _write(tmp_path, "datasets/old.jsonl", "{}\n")
    assert layout.resolve(tmp_path, "datasets/old.jsonl") == tmp_path / "datasets/old.jsonl"
    _write(tmp_path, "platform/datasets/new.jsonl", "{}\n")
    assert (
        layout.resolve(tmp_path, "datasets/new.jsonl") == tmp_path / "platform/datasets/new.jsonl"
    )


def test_referee_mutants_are_read_from_either_layout(two_layouts: tuple[Path, str, str]) -> None:
    from shipharness.ab.mutants import load_referee_mutants

    repo, _, _ = two_layouts
    real = (layout.REPO_ROOT / layout.APP_DIR / "mutants" / "features" / "f1.jsonl").read_text(
        encoding="utf-8"
    )
    _git(repo, "checkout", "-q", "HEAD~1")
    _write(repo, "teamtrack/mutants/features/f1.jsonl", real)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "old layout with mutants")
    old = _git(repo, "rev-parse", "HEAD")
    expected = load_referee_mutants("features/f1", layout.REPO_ROOT)
    assert expected
    from_old = load_referee_mutants("features/f1", repo, ref=old)
    assert [m.id for m in from_old] == [m.id for m in expected]
    from_working_tree = load_referee_mutants("features/f1", repo)  # an old-layout checkout
    assert [m.id for m in from_working_tree] == [m.id for m in expected]


def test_checkpoint_trees_use_teamtrack_in_either_layout(
    two_layouts: tuple[Path, str, str],
) -> None:
    from shipharness import freeze

    repo, old, new = two_layouts
    _git(repo, "tag", "m1-old", old)
    _git(repo, "tag", "m1-new", new)
    trees = freeze.checkpoint_trees(repo)
    assert trees["m1-old"] == _git(repo, "rev-parse", f"{old}:teamtrack")
    assert trees["m1-new"] == _git(repo, "rev-parse", f"{new}:platform/teamtrack")


@pytest.mark.parametrize("app_dir", ["platform/teamtrack", "teamtrack"])
def test_checkpoint_commits_patch_teamtrack_where_head_has_it(tmp_path: Path, app_dir: str) -> None:
    from shipharness.ab.checkpoints import build_commits, load_task, task_names

    repo = tmp_path / "repo"
    _write(repo, f"{app_dir}/app/x.py", "a = 1\n")
    _write(
        repo,
        f"{app_dir}/reference/f1/f1.patch",
        "diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n"
        "@@ -1 +1,2 @@\n a = 1\n+b = 2\n",
    )
    _write(
        repo,
        f"{app_dir}/reference/checkpoints.toml",
        '[checkpoints."m1-s1-start"]\ntasks = []\n\n[checkpoints."m1-s2-start"]\ntasks = ["f1"]\n',
    )
    _write(
        repo,
        f"{app_dir}/reference/f1/task.toml",
        'id = "F1"\ntitle = "t"\nsection = "demo-1"\nstart_checkpoint = "m1-s1-start"\n'
        'mutant_set = "features/f1"\nsession_budget = [1]\ncanonical_ticket = "x"\n'
        '[allowed_paths]\nbuild = ["app/**"]\ntest = ["tests/**"]\n',
    )
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@t.invalid")
    _git(repo, "commit", "-q", "-m", "base")
    build_commits(repo, dry_run=False)
    assert _git(repo, "show", f"m1-s2-start:{app_dir}/app/x.py") == "a = 1\nb = 2"
    assert task_names(repo) == ["f1"]
    assert load_task("f1", repo).start_checkpoint == "m1-s1-start"
