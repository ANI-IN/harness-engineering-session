"""The verify loop must fail on a failing verify.sh and on an empty discovery."""

from pathlib import Path

from tools import run_verify


def _script(root: Path, rel: str, exit_code: int) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env bash\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_failing_verify_sh_fails_the_target(tmp_path):
    _script(tmp_path, "lectures/lecture-01-x/verify.sh", 1)
    assert run_verify.run_all(tmp_path, floor=1) == 1


def test_passing_verify_sh_passes(tmp_path):
    _script(tmp_path, "lectures/lecture-01-x/verify.sh", 0)
    assert run_verify.run_all(tmp_path, floor=1) == 0


def test_one_failure_among_many_still_fails(tmp_path):
    _script(tmp_path, "lectures/lecture-01-x/verify.sh", 0)
    _script(tmp_path, "projects/project-01-y/verify.sh", 1)
    assert run_verify.run_all(tmp_path, floor=1) == 1


def test_below_floor_fails(tmp_path):
    (tmp_path / "lectures").mkdir()
    assert run_verify.run_all(tmp_path, floor=1) == 1
