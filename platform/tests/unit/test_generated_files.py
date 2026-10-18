"""Tool caches are not product changes (M6 pilot: `.import_linter_cache/` in every arm's diff).

Running the import linter writes four cache files into the workspace. They showed up as out-of-scope
files and test-phase source edits in every arm, the scope layer reverted them after every lint run,
and the referee counted them against the S3 measure for both arms.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shipharness.harness.verify.clean_state import _generated
from shipharness.runner import git as run_git
from shipharness.runner.tools import SKIP_DIRS, iter_workspace_files

CACHE_FILES = (
    ".import_linter_cache/.gitignore",
    ".import_linter_cache/CACHEDIR.TAG",
    ".import_linter_cache/app.meta.json",
)


def _repo(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "app.py").write_text("a = 1\n", encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
    subprocess.run(["git", *ident, "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "commit", "-qm", "base"], cwd=ws, check=True)
    return ws


def _write_cache(ws: Path) -> None:
    for rel in CACHE_FILES:
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")


def test_import_linter_cache_is_left_out_of_the_diff(tmp_path: Path) -> None:
    ws = _repo(tmp_path)
    base = run_git.head_sha(ws)
    _write_cache(ws)
    (ws / "app.py").write_text("a = 2\n", encoding="utf-8")
    assert run_git.changed_files(ws, base) == ["app.py"]
    out = run_git.write_diff(ws, base, tmp_path / "diff.patch")
    assert out is not None and b"import_linter_cache" not in out.read_bytes()


def test_import_linter_cache_is_skipped_by_workspace_snapshots(tmp_path: Path) -> None:
    ws = _repo(tmp_path)
    _write_cache(ws)
    names = [p.relative_to(ws).as_posix() for p in iter_workspace_files(ws)]
    assert names == ["app.py"]


def test_import_linter_cache_is_generated_for_the_clean_state_check() -> None:
    assert all(_generated(rel) for rel in CACHE_FILES)


def test_every_skipped_cache_directory_is_also_left_out_of_diffs() -> None:
    patterns = set(run_git.GENERATED_PATTERNS)
    for name in SKIP_DIRS - {".git"}:
        assert f"**/{name}/**" in patterns, name
        assert _generated(f"{name}/x"), name
