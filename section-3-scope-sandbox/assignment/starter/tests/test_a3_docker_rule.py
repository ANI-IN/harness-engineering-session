"""Optional: the history rule in a real container. Run with: pytest -m docker.

Needs Docker (or Podman) and the agent image from `make setup`
(docker build -f sandbox/Dockerfile --target agent -t shipharness-agent:1 .).
Not graded; the graded denial test is test_a3_sandbox_rule.py, which needs no container.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from a3scope.policy import policy

from shipharness.sandbox import DockerSandbox

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed"),
]

IMAGE = "shipharness-agent:1"
GIT = "git -c user.name=a3 -c user.email=a3@example.invalid"


@pytest.fixture
def box(tmp_path: Path):  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    workspace.mkdir()
    workspace.chmod(0o777)
    sandbox = DockerSandbox(policy(), IMAGE, workspace, None, "a3-docker", "harness")
    sandbox.start()
    try:
        yield sandbox
    finally:
        sandbox.stop()


def test_amend_is_denied_in_a_real_container_and_history_is_unchanged(box) -> None:  # type: ignore[no-untyped-def]
    setup = box.exec(f"git init -q && {GIT} commit -q --allow-empty -m first", timeout_s=60)
    assert setup.exit_code == 0, setup.output
    result = box.exec(f"{GIT} commit -q --amend --allow-empty -m rewritten", timeout_s=60)
    assert result.exit_code == 126
    assert result.denied is not None and result.denied.reason_code == "write_outside_workspace"
    log = box.exec("git log --format=%s", timeout_s=60)
    assert log.output.split() == ["first"]


def test_an_ordinary_commit_still_runs_in_a_real_container(box) -> None:  # type: ignore[no-untyped-def]
    assert (
        box.exec(f"git init -q && {GIT} commit -q --allow-empty -m a", timeout_s=60).exit_code == 0
    )
    assert box.exec(f"{GIT} commit -q --allow-empty -m b", timeout_s=60).exit_code == 0
    assert box.exec("git log --format=%s", timeout_s=60).output.split() == ["b", "a"]
