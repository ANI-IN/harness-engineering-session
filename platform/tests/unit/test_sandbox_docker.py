"""Integration tests against a real container runtime. Run with: pytest -m docker.

Needs the agent image: docker build -f sandbox/Dockerfile --target agent -t shipharness-agent:1 .
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from shipharness.config import Settings
from shipharness.events import EventBus, read_events
from shipharness.layout import find_repo_root
from shipharness.sandbox import DockerSandbox, default_policy

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed"),
]


@pytest.fixture
def sandbox(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(_env_file=None)
    log = tmp_path / "events.jsonl"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    workspace.chmod(0o777)
    with EventBus(log, ab_id=None) as bus:
        box = DockerSandbox(
            default_policy(settings), settings.sandbox_image_agent, workspace, bus, "r-1", "bare"
        )
        box.start()
        try:
            yield box, log, workspace
        finally:
            box.stop()


def test_workspace_is_writable(sandbox) -> None:  # type: ignore[no-untyped-def]
    box, _log, workspace = sandbox
    assert box.exec("echo hi > out.txt && cat out.txt", timeout_s=30).exit_code == 0
    assert (workspace / "out.txt").read_text().strip() == "hi"


def test_network_is_off_and_denial_is_reported(sandbox) -> None:  # type: ignore[no-untyped-def]
    box, log, _ = sandbox
    cmd = "python -c \"import socket; socket.create_connection(('example.com', 80), timeout=3)\""
    result = box.exec(cmd, timeout_s=30)
    assert result.exit_code != 0
    assert result.denied is not None and result.denied.reason_code == "network"
    assert any(e.type == "sandbox_denied" for e in read_events(log))


def test_root_filesystem_is_read_only(sandbox) -> None:  # type: ignore[no-untyped-def]
    box, _log, _ = sandbox
    result = box.exec("touch /etc/shipharness-test", timeout_s=30)
    assert result.denied is not None
    assert result.denied.reason_code == "write_outside_workspace"


def test_runs_as_non_root(sandbox) -> None:  # type: ignore[no-untyped-def]
    box, _log, _ = sandbox
    assert box.exec("id -u", timeout_s=30).output.strip() == "1000"


def test_timeout_is_enforced(sandbox) -> None:  # type: ignore[no-untyped-def]
    box, _log, _ = sandbox
    result = box.exec("sleep 30", timeout_s=2)
    assert result.timed_out is True


def _box(tmp_path: Path, name: str, **policy_update: object) -> tuple[DockerSandbox, Path]:
    settings = Settings(_env_file=None)
    workspace = tmp_path / name
    workspace.mkdir()
    workspace.chmod(0o777)
    policy = default_policy(settings).model_copy(update=policy_update)
    box = DockerSandbox(policy, settings.sandbox_image_agent, workspace, None, f"r-{name}", "bare")
    return box, workspace


def test_preview_workspace_mount_is_read_only(tmp_path: Path) -> None:
    """Board previews mount the arm workspace read-only: they can never change the arm's diff."""
    box, workspace = _box(tmp_path, "preview", workspace_read_only=True)
    (workspace / "app.py").write_text("x = 1\n", encoding="utf-8")
    box.start()
    try:
        assert box.exec("cat /work/app.py", timeout_s=30).output.strip() == "x = 1"
        write = box.exec("echo y > /work/app.py; touch /work/new.txt", timeout_s=30)
        assert write.exit_code != 0
        assert box.exec("echo ok > /tmp/scratch && cat /tmp/scratch", timeout_s=30).exit_code == 0
    finally:
        box.stop()
    assert (workspace / "app.py").read_text(encoding="utf-8") == "x = 1\n"
    assert not (workspace / "new.txt").exists()


def test_harness_commands_keep_limits_above_the_tool_cap(tmp_path: Path) -> None:
    """The referee and the gate pass their own, longer limits; only agent tool calls are capped."""
    box, _workspace = _box(tmp_path, "harness", tool_timeout_s=1)
    box.start()
    try:
        result = box.exec("sleep 3 && echo finished", timeout_s=30)
        assert result.timed_out is False
        assert result.exit_code == 0 and result.output.strip() == "finished"
    finally:
        box.stop()


def test_read_only_extra_mount_inside_the_workspace(tmp_path: Path) -> None:
    """The referee mounts hidden tests read-only inside /work; the build cannot change them."""
    settings = Settings(_env_file=None)
    workspace = tmp_path / "build"
    workspace.mkdir()
    workspace.chmod(0o777)
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "test_secret.py").write_text("def test_secret():\n    assert 1\n", encoding="utf-8")
    box = DockerSandbox(
        default_policy(settings),
        settings.sandbox_image_agent,
        workspace,
        None,
        "r-ro",
        "bare",
        extra_mounts=[(hidden, "/work/tests/hidden", "ro")],
    )
    box.start()
    try:
        assert box.exec("cat tests/hidden/test_secret.py", timeout_s=30).exit_code == 0
        assert box.exec("echo x >> tests/hidden/test_secret.py", timeout_s=30).exit_code != 0
    finally:
        box.stop()
    assert "x" not in (hidden / "test_secret.py").read_text(encoding="utf-8").split()


def test_preview_reloads_the_arms_code_and_captures_the_board(tmp_path: Path) -> None:
    """The preview runs the arm's TeamTrack from the read-only workspace mount, reloads when the
    arm changes app/, and the trusted capture script screenshots the board in the container."""
    import time

    from shipharness.ab.workspace import export_checkpoint
    from shipharness.console.preview import BoardPreview

    repo = find_repo_root(Path(__file__))
    workspace = export_checkpoint(repo, None, tmp_path / "ws")
    settings = Settings(_env_file=None)
    policy = default_policy(settings).model_copy(update={"workspace_read_only": True})
    log = tmp_path / "run" / "events.jsonl"
    log.parent.mkdir()
    with EventBus(log, ab_id=None) as bus:
        box = DockerSandbox(
            policy, settings.sandbox_image_referee, workspace, bus, "r-preview", "bare"
        )
        box.start()
        try:
            preview = BoardPreview(box, bus, log.parent, run_id="r-preview", arm="bare")
            preview.start_server()
            probe = (
                'python -c "import urllib.request;'
                "print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())\""
            )
            assert '"ok"' in box.exec(probe, timeout_s=30).output
            health = workspace / "app" / "api" / "health.py"
            health.write_text(
                health.read_text(encoding="utf-8").replace('status="ok"', 'status="reloaded"'),
                encoding="utf-8",
            )
            seen = ""
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and '"reloaded"' not in seen:
                time.sleep(1)
                seen = box.exec(probe, timeout_s=30).output
            assert '"reloaded"' in seen, seen[-300:]
            event = preview.capture("board")
            assert event is not None, preview.last_error
            png = log.parent / event.data["path"]
            assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        finally:
            box.stop()


def test_commands_see_the_image_dependencies(sandbox) -> None:  # type: ignore[no-untyped-def]
    """Agent, gate, and referee commands run with the image's virtual environment: pytest, the
    TeamTrack stack, and the image's check runner import (a login shell would reset PATH)."""
    box, _log, _ = sandbox
    result = box.exec(
        "python -c 'import pytest, fastapi, sqlalchemy, alembic, uvicorn; print(\"deps ok\")'",
        timeout_s=60,
    )
    assert result.exit_code == 0, result.output[-500:]
    assert "deps ok" in result.output
    runner = box.exec("python -P -m shipharness.checks.runner --help", timeout_s=60)
    assert runner.exit_code == 0, runner.output[-500:]


def test_check_runner_judges_teamtrack_inside_the_referee_container(tmp_path: Path) -> None:
    """The referee path end to end in a real container: the image's runner (python -P), the
    checkpoint export as working directory, migrations, layering, and the existing tests."""
    from shipharness.ab.workspace import export_checkpoint
    from shipharness.harness.verify.checkrun import (
        new_nonce,
        parse_runner_output,
        runner_command,
    )

    repo = find_repo_root(Path(__file__))
    build = export_checkpoint(repo, None, tmp_path / "build")
    build.chmod(0o777)
    settings = Settings(_env_file=None)
    box = DockerSandbox(
        default_policy(settings), settings.sandbox_image_referee, build, None, "r-ref", "bare"
    )
    box.start()
    try:
        nonce = new_nonce()
        command = runner_command(
            build=".",
            checks=["r6_layering", "r7_migrations", "regression"],
            checkpoint="m1-s1-start",
            feature="F1",
            seed=7,
            nonce=nonce,
        )
        output = box.exec(command, timeout_s=900)
        results, _progress = parse_runner_output(output.output, nonce=nonce)
    finally:
        box.stop()
    by_check = {r.check: r for r in results}
    assert set(by_check) == {"r6_layering", "r7_migrations", "regression"}
    assert all(r.passed for r in results), [(r.check, r.findings[:2]) for r in results]
    assert by_check["regression"].total_probes >= 100


@pytest.mark.parametrize(
    ("image", "profile", "cpus"),
    [("agent", "standard", 1.0), ("agent", "class", 2.0), ("referee", "class", 2.0)],
)
def test_the_profile_cpu_limit_is_applied_in_a_real_container(
    tmp_path: Path, image: str, profile: str, cpus: float
) -> None:
    """Class profile: every arm and referee container gets 2 CPUs; standard keeps 1."""
    import subprocess

    from shipharness.config.profiles import apply_profile

    settings = apply_profile(Settings(_env_file=None), profile)
    name = settings.sandbox_image_agent if image == "agent" else settings.sandbox_image_referee
    workspace = tmp_path / "ws"
    workspace.mkdir()
    workspace.chmod(0o777)
    box = DockerSandbox(default_policy(settings), name, workspace, None, "r-cpu", "harness")
    box.start()
    try:
        result = box.exec("cat /sys/fs/cgroup/cpu.max", timeout_s=30)
        assert result.exit_code == 0, result.output
        quota, period = result.output.split()
        assert int(quota) / int(period) == cpus  # the kernel's CPU bandwidth limit (cgroup v2)
        inspect = subprocess.run(
            ["docker", "inspect", "--format", "{{.HostConfig.NanoCpus}}", box.name],
            capture_output=True,
            text=True,
            check=True,
        )
        assert int(inspect.stdout.strip()) == int(cpus * 1e9)
    finally:
        box.stop()
