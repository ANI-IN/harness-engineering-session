"""Where things live in the course repository (the course-first layout).

The repository root holds the course (section folders, setup/, docs/, slides/, use-in-your-repo/);
the code and data the course runs on live under `platform/`: the shipharness package
(`platform/src`), TeamTrack (`platform/teamtrack`), the sandbox, config, datasets, tests, and
scripts. The root is found by its marker file (`pyproject.toml`), never by a fixed depth, so a
file can move without breaking the lookup.

Recorded A/B results pin checkpoint commits made before this layout, whose tree has TeamTrack at
`teamtrack/`. Every reader of a checkpoint tree resolves the app directory per commit
(`app_dir_at`), so a swap or replay of an older A/B still exports the tree its arms started from.
Data files (task manifests, datasets) name TeamTrack and dataset files by their logical paths
(`teamtrack/...`, `datasets/...`); `logical_path` maps them to the current layout.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_MARKER = "pyproject.toml"
PLATFORM_DIR = "platform"
APP_DIR = f"{PLATFORM_DIR}/teamtrack"
LEGACY_APP_DIR = "teamtrack"  # checkpoint commits made before the course-first layout
DATASETS_DIR = f"{PLATFORM_DIR}/datasets"
# Logical top-level names used in data files -> where they live now.
_LOGICAL = {"teamtrack": APP_DIR, "datasets": DATASETS_DIR}


class RepoRootNotFound(LookupError):
    pass


def find_repo_root(start: Path, marker: str = REPO_MARKER) -> Path:
    """The nearest directory at or above `start` that holds `marker`."""
    start = Path(start).resolve()
    for folder in (start, *start.parents):
        if (folder / marker).is_file():
            return folder
    raise RepoRootNotFound(f"no {marker} at or above {start}")


def _default_root() -> Path:
    here = Path(__file__).resolve()
    try:
        return find_repo_root(here.parent)
    except RepoRootNotFound:  # an installed copy (the sandbox image): no course repository
        return Path.cwd()


REPO_ROOT = _default_root()


def _has_tree(repo: Path, ref: str, path: str) -> bool:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    done = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        cwd=repo,
        capture_output=True,
        env=env,
        check=False,
    )
    return done.returncode == 0


def app_dir_at(repo: Path, ref: str | None = None) -> str:
    """TeamTrack's directory in `repo` at `ref` (None: the working tree): `platform/teamtrack`,
    or `teamtrack` for a commit (or a checkout) in the layout before the course-first one."""
    if ref is None:
        if (Path(repo) / APP_DIR).is_dir() or not (Path(repo) / LEGACY_APP_DIR).is_dir():
            return APP_DIR
        return LEGACY_APP_DIR
    if _has_tree(Path(repo), ref, APP_DIR) or not _has_tree(Path(repo), ref, LEGACY_APP_DIR):
        return APP_DIR
    return LEGACY_APP_DIR


def logical_path(rel: str, app_dir: str = APP_DIR) -> str:
    """A repository-relative path from a data file (`teamtrack/mutants/x.jsonl`,
    `datasets/mutants/boltons/x.jsonl`) in the current layout; other paths are unchanged."""
    head, sep, rest = rel.partition("/")
    if head == "teamtrack":
        return f"{app_dir}{sep}{rest}" if sep else app_dir
    if head in _LOGICAL:
        return f"{_LOGICAL[head]}{sep}{rest}"
    return rel


def resolve(root: Path, rel: str) -> Path:
    """`rel` (a logical or a current path) under the checkout `root`: the current layout when the
    file is there, else `rel` as written (a checkout in the layout before the course-first one)."""
    moved = Path(root) / logical_path(rel, app_dir_at(root))
    return moved if moved.exists() or not (Path(root) / rel).exists() else Path(root) / rel
