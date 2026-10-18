"""Host-side git for an arm's workspace. The workspace is untrusted.

The agent controls `.git/config` (it runs commands in the sandbox), so host git must never read it:
config such as `core.fsmonitor`, filter drivers, `diff.external`, or textconv would make host git
execute agent-chosen commands outside the sandbox. Every command here runs against a temporary git
directory with a clean config that borrows the workspace's objects through `objects/info/alternates`
(object data only), with system and global config disabled. Output is handled as bytes.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")

# The diff is what the referee judges, so the agent's own ignore files (.gitignore) must not decide
# what it contains: files are added with --force, and only this fixed list of generated files is
# left out (decision for review finding M12).
GENERATED_PATTERNS: tuple[str, ...] = (
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    "**/.mypy_cache/**",
    "**/.import_linter_cache/**",
    "**/.venv/**",
    "**/node_modules/**",
    "**/.coverage",
    "**/*.db",
    "**/*.sqlite",
    "**/*.sqlite3",
)
_GENERATED_EXCLUDES = [f":(exclude,glob){pattern}" for pattern in GENERATED_PATTERNS]


def _clean_env(home: Path) -> dict[str, str]:
    keep = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {
        **keep,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "HOME": str(home),
        "GIT_TERMINAL_PROMPT": "0",
    }


def workspace_git_dir(workspace: Path) -> Path | None:
    """The workspace's .git directory, if it is a real directory inside the workspace."""
    root = Path(workspace).resolve()
    git_dir = Path(workspace) / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        return None
    if getattr(git_dir, "is_junction", lambda: False)():
        return None
    resolved = git_dir.resolve()
    if root not in resolved.parents:
        return None
    return resolved


def _read_ref(git_dir: Path, ref: str, depth: int = 0) -> str:
    """Resolve HEAD or a ref by reading files (no git process touches the agent's config)."""
    if depth > 5:
        return ""
    path = git_dir / ref
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("ref: "):
            return _read_ref(git_dir, text[5:].strip(), depth + 1)
        return text if _SHA.match(text) else ""
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref and _SHA.match(parts[0]):
                return parts[0]
    return ""


@contextmanager
def _isolated(workspace: Path) -> Iterator[tuple[list[str], dict[str, str], Path] | None]:
    """Yield (git argv prefix, env, temp dir) for a clean repo that sees the workspace objects."""
    git_dir = workspace_git_dir(workspace)
    if git_dir is None:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix="shipharness-git-") as tmp:
        tmp_path = Path(tmp)
        env = _clean_env(tmp_path)
        repo = tmp_path / "repo"
        init = subprocess.run(
            ["git", "init", "-q", str(repo)], capture_output=True, env=env, check=False
        )
        if init.returncode != 0:
            yield None
            return
        alternates = repo / ".git" / "objects" / "info" / "alternates"
        alternates.write_bytes(((git_dir / "objects").as_posix() + "\n").encode("utf-8"))
        prefix = [
            "git",
            "--git-dir",
            str(repo / ".git"),
            "--work-tree",
            str(Path(workspace).resolve()),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "core.autocrlf=false",
            "-c",
            "safe.directory=*",
        ]
        yield prefix, {**env, "GIT_INDEX_FILE": str(tmp_path / "index")}, tmp_path


def head_sha(workspace: Path) -> str:
    git_dir = workspace_git_dir(workspace)
    return _read_ref(git_dir, "HEAD") if git_dir else ""


def initial_sha(workspace: Path) -> str:
    """Root commit of the workspace history (the checkpoint commit)."""
    head = head_sha(workspace)
    if not head:
        return ""
    with _isolated(workspace) as isolated:
        if isolated is None:
            return ""
        prefix, env, _tmp = isolated
        out = subprocess.run(
            [*prefix, "rev-list", "--max-parents=0", head],
            capture_output=True,
            env=env,
            check=False,
        )
    lines = out.stdout.decode("ascii", errors="replace").split()
    return lines[-1] if out.returncode == 0 and lines else ""


def root_tree(workspace: Path) -> str:
    """Tree id of the root commit: the checkpoint's content (same for every arm that starts from
    it, whatever the commit id). Empty string without one."""
    root = initial_sha(workspace)
    if not root:
        return ""
    with _isolated(workspace) as isolated:
        if isolated is None:
            return ""
        prefix, env, _tmp = isolated
        out = subprocess.run(
            [*prefix, "rev-parse", f"{root}^{{tree}}"], capture_output=True, env=env, check=False
        )
    sha = out.stdout.decode("ascii", errors="replace").strip()
    return sha if out.returncode == 0 and _SHA.match(sha) else ""


def changed_files(workspace: Path, base_sha: str) -> list[str]:
    """Paths whose content differs between `base_sha` and the working tree (untracked files
    included, generated files excluded). Same isolation as write_diff."""
    if not base_sha or not _SHA.match(base_sha):
        return []
    with _isolated(workspace) as isolated:
        if isolated is None:
            return []
        prefix, env, _tmp = isolated
        add = [*prefix, "add", "-A", "--force", "--", ".", *_GENERATED_EXCLUDES]
        if subprocess.run(add, capture_output=True, env=env, check=False).returncode != 0:
            return []
        names = subprocess.run(
            [*prefix, "diff", "--cached", "--name-only", "-z", "--no-renames", base_sha],
            capture_output=True,
            env=env,
            check=False,
        )
    if names.returncode != 0:
        return []
    return [n.decode("utf-8", errors="replace") for n in names.stdout.split(b"\0") if n]


def write_range_diff(workspace: Path, from_sha: str, to_sha: str, out_path: Path) -> Path | None:
    """Binary-safe diff between two commits of the workspace (per-session patches)."""
    if not (_SHA.match(from_sha or "") and _SHA.match(to_sha or "")):
        return None
    with _isolated(workspace) as isolated:
        if isolated is None:
            return None
        prefix, env, _tmp = isolated
        diff = subprocess.run(
            [*prefix, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-color"]
            + [from_sha, to_sha, "--", ".", *_GENERATED_EXCLUDES],
            capture_output=True,
            env=env,
            check=False,
        )
    if diff.returncode != 0:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(diff.stdout)
    return out_path


def write_diff(workspace: Path, base_sha: str, out_path: Path) -> Path | None:
    """Binary-safe diff of the working tree (including untracked files) against `base_sha`."""
    if not base_sha or not _SHA.match(base_sha):
        return None
    with _isolated(workspace) as isolated:
        if isolated is None:
            return None
        prefix, env, _tmp = isolated
        if (
            subprocess.run(
                [*prefix, "add", "-A", "--force", "--", ".", *_GENERATED_EXCLUDES],
                capture_output=True,
                env=env,
                check=False,
            ).returncode
            != 0
        ):
            return None
        diff = subprocess.run(
            [
                *prefix,
                "diff",
                "--cached",
                "--binary",
                "--no-ext-diff",
                "--no-textconv",
                "--no-color",
                base_sha,
            ],
            capture_output=True,
            env=env,
            check=False,
        )
    if diff.returncode != 0:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(diff.stdout)
    return out_path


def _store_prefix(store: Path, workspace: Path) -> list[str]:
    return [
        "git",
        "--git-dir",
        str(store),
        "--work-tree",
        str(Path(workspace).resolve()),
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "core.autocrlf=false",
        "-c",
        "safe.directory=*",
    ]


def snapshot_tree(workspace: Path, store: Path) -> str:
    """Tree id of the whole working tree (committed or not, untracked files included, generated
    files excluded), written into `store`: a bare git directory outside the workspace that borrows
    the workspace objects through alternates. Session snapshots make the S2 measure independent of
    whether the arm commits. Never reads the workspace's git config. Empty string on failure."""
    store = Path(store)
    with tempfile.TemporaryDirectory(prefix="shipharness-snap-") as tmp:
        env = _clean_env(Path(tmp))
        if not (store / "HEAD").is_file():
            store.parent.mkdir(parents=True, exist_ok=True)
            init = subprocess.run(
                ["git", "init", "-q", "--bare", str(store)],
                capture_output=True,
                env=env,
                check=False,
            )
            if init.returncode != 0:
                return ""
            git_dir = workspace_git_dir(workspace)
            if git_dir is not None:
                alternates = store / "objects" / "info" / "alternates"
                alternates.write_bytes(((git_dir / "objects").as_posix() + "\n").encode("utf-8"))
        prefix = _store_prefix(store, workspace)
        env = {**env, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        add = [*prefix, "add", "-A", "--force", "--", ".", *_GENERATED_EXCLUDES]
        if subprocess.run(add, capture_output=True, env=env, check=False).returncode != 0:
            return ""
        tree = subprocess.run([*prefix, "write-tree"], capture_output=True, env=env, check=False)
    sha = tree.stdout.decode("ascii", errors="replace").strip()
    return sha if tree.returncode == 0 and _SHA.match(sha) else ""


def tree_changed_files(store: Path, from_tree: str, to_tree: str) -> list[str]:
    """Paths that differ between two snapshot trees of `store`."""
    if not (_SHA.match(from_tree or "") and _SHA.match(to_tree or "")):
        return []
    with tempfile.TemporaryDirectory(prefix="shipharness-snap-") as tmp:
        names = subprocess.run(
            ["git", "--git-dir", str(store), "diff", "--name-only", "-z", "--no-renames"]
            + [from_tree, to_tree],
            capture_output=True,
            env=_clean_env(Path(tmp)),
            check=False,
        )
    if names.returncode != 0:
        return []
    return sorted(n.decode("utf-8", errors="replace") for n in names.stdout.split(b"\0") if n)


def write_tree_diff(store: Path, from_tree: str, to_tree: str, out_path: Path) -> Path | None:
    """Binary-safe diff between two snapshot trees of `store` (per-session patches)."""
    if not (_SHA.match(from_tree or "") and _SHA.match(to_tree or "")):
        return None
    with tempfile.TemporaryDirectory(prefix="shipharness-snap-") as tmp:
        env = _clean_env(Path(tmp))
        diff = subprocess.run(
            ["git", "--git-dir", str(store), "-c", "core.autocrlf=false", "diff", "--binary"]
            + ["--no-ext-diff", "--no-textconv", "--no-color", from_tree, to_tree],
            capture_output=True,
            env=env,
            check=False,
        )
    if diff.returncode != 0:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(diff.stdout)
    return out_path
