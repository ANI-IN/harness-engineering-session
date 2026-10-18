from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
SCRIPT = REPO / "platform" / "scripts" / "anchors.py"

M3_ANCHORS = ["Opening:publish", "S1:progressive", "S3:policy", "S3:dockerfile"]


def run(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_repository_anchors_are_valid() -> None:
    result = run("check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_m3_anchors_exist_and_extract_code() -> None:
    for anchor in M3_ANCHORS:
        result = run("extract", anchor)
        assert result.returncode == 0, (anchor, result.stderr)
        assert result.stdout.strip(), anchor
        assert "[walkthrough:" not in result.stdout


def test_unknown_anchor_fails() -> None:
    assert run("extract", "S9:nothing").returncode != 0


def test_check_rejects_unbalanced_and_long_anchors(tmp_path: Path) -> None:
    src = tmp_path / "platform" / "src"
    src.mkdir(parents=True)
    (src / "a.py").write_text("# [walkthrough:S1:open] start\nx = 1\n", encoding="utf-8")
    body = "\n".join(f"y{i} = {i}" for i in range(45))
    (src / "b.py").write_text(
        f"# [walkthrough:S2:long] start\n{body}\n# [walkthrough:S2:long] end\n", encoding="utf-8"
    )
    result = run("check", "--root", str(tmp_path))
    assert result.returncode == 1
    assert "S1:open" in result.stdout and "S2:long" in result.stdout
