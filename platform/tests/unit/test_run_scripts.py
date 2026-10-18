"""Every demo and final-project run.sh works from any folder and fails early with a clear message.

No test here starts a run: each case stops before `make` (bad argument, missing key, no Docker).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = sorted(REPO.glob("section-*/demo/run.sh")) + [REPO / "final-project" / "run.sh"]
IDS = [p.relative_to(REPO).as_posix() for p in SCRIPTS]
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None or os.name == "nt", reason="needs bash on POSIX")


def test_every_section_has_a_demo_script() -> None:
    assert len(SCRIPTS) == 5, IDS


@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_shebang_strict_mode_and_cd_to_root(script: Path) -> None:
    lines = script.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#!/usr/bin/env bash"
    assert "set -euo pipefail" in lines
    depth = len(script.relative_to(REPO).parts) - 1
    up = "/".join([".."] * depth)
    assert f'ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/{up}" && pwd)"' in lines
    assert 'cd "$ROOT"' in lines
    root_at = lines.index('cd "$ROOT"')
    assert lines.index("set -euo pipefail") < root_at
    assert not [line for line in lines[:root_at] if line.startswith(("make ", "exec "))]


@needs_bash
@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_syntax(script: Path) -> None:
    assert subprocess.run([BASH, "-n", str(script)], check=False).returncode == 0  # type: ignore[list-item]


def _fake_repo(tmp_path: Path, script: Path, env_text: str | None) -> Path:
    """A copy of the script at the same depth under a fake root, with its own .env."""
    rel = script.relative_to(REPO)
    copy = tmp_path / "repo" / rel
    copy.parent.mkdir(parents=True)
    shutil.copy(script, copy)
    if env_text is not None:
        (tmp_path / "repo" / ".env").write_text(env_text, encoding="utf-8")
    return copy


def _tools_dir(tmp_path: Path, *, docker: str | None) -> Path:
    """A PATH with only the tools the checks use, and a docker that is absent or fails."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("dirname", "grep", "cut", "tr", "tail", "date", "sed", "curl"):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    if docker is not None:
        fake = bin_dir / "docker"
        fake.write_text(f"#!{BASH}\n{docker}\n", encoding="utf-8")
        fake.chmod(0o755)
    return bin_dir


def _run(copy: Path, tmp_path: Path, path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": path, "HOME": str(tmp_path), "PURPOSE": "pilot"}
    return subprocess.run(
        [BASH, str(copy), *args],  # type: ignore[list-item]
        cwd="/tmp" if Path("/tmp").is_dir() else tmp_path,  # any folder outside the repository
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@needs_bash
@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_a_bad_argument_stops_with_usage(script: Path, tmp_path: Path) -> None:
    copy = _fake_repo(tmp_path, script, "OPENAI_API_KEY=x\nLANGSMITH_API_KEY=y\n")
    result = _run(copy, tmp_path, str(_tools_dir(tmp_path, docker=None)), "--bogus")
    assert result.returncode == 2
    assert "unknown argument '--bogus'" in result.stderr
    assert "PURPOSE=pilot" in result.stderr
    help_result = _run(copy, tmp_path, str(tmp_path / "bin"), "--help")
    assert help_result.returncode == 0 and "Usage" in help_result.stdout


@needs_bash
@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_a_missing_key_is_named(script: Path, tmp_path: Path) -> None:
    copy = _fake_repo(tmp_path, script, "OPENAI_API_KEY=\nLANGSMITH_API_KEY=y\n")
    result = _run(copy, tmp_path, str(_tools_dir(tmp_path, docker=None)))
    assert result.returncode == 2
    assert "OPENAI_API_KEY is not set" in result.stderr
    assert "make doctor" in result.stderr


@needs_bash
@pytest.mark.parametrize("script", SCRIPTS, ids=IDS)
def test_docker_missing_or_stopped_is_reported(script: Path, tmp_path: Path) -> None:
    copy = _fake_repo(tmp_path, script, "OPENAI_API_KEY=x\nLANGSMITH_API_KEY=y\n")
    absent = _run(copy, tmp_path, str(_tools_dir(tmp_path, docker=None)))
    assert absent.returncode == 2
    assert "docker not found" in absent.stderr
    shutil.rmtree(tmp_path / "bin")
    stopped = _run(copy, tmp_path, str(_tools_dir(tmp_path, docker="exit 1")))
    assert stopped.returncode == 2
    assert "Docker is not running" in stopped.stderr
