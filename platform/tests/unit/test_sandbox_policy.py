from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import Settings
from shipharness.events import EventBus, read_events
from shipharness.sandbox import (
    DockerSandbox,
    check_command,
    default_policy,
    detect_denial,
    docker_run_args,
    render_policy,
)

from .fakes import fake_langsmith_key, fake_openai_key


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENAI_API_KEY", fake_openai_key())
    monkeypatch.setenv("LANGSMITH_API_KEY", fake_langsmith_key())
    return Settings(_env_file=None)


def test_run_args_apply_every_limit(settings: Settings, tmp_path: Path) -> None:
    args = docker_run_args(default_policy(settings), "img:1", tmp_path, "arm-bare")
    joined = " ".join(args)
    for expected in (
        "--network none",
        "--memory 1024m",
        "--memory-swap 1024m",
        "--cpus 1.0",
        "--pids-limit 256",
        "--read-only",
        "--tmpfs /tmp:rw,nosuid,size=256m",
        "--user 1000:1000",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--init",
        f"{tmp_path.resolve()}:/work",
        "-w /work",
    ):
        assert expected in joined, expected
    assert args[:3] == ["docker", "run", "-d"]
    assert args[-3:] == ["img:1", "sleep", "infinity"]


def test_run_args_never_carry_host_env_or_keys(settings: Settings, tmp_path: Path) -> None:
    args = docker_run_args(
        default_policy(settings), "img:1", tmp_path, "arm", env={"TEAMTRACK_DB": "/work/t.db"}
    )
    assert "--env-file" not in args
    joined = " ".join(args)
    assert fake_openai_key() not in joined
    assert fake_langsmith_key() not in joined
    env_names = [args[i + 1].split("=", 1)[0] for i, a in enumerate(args) if a == "-e"]
    assert "TEAMTRACK_DB" in env_names
    assert all(not any(w in n.upper() for w in ("KEY", "TOKEN", "SECRET")) for n in env_names)


def test_run_args_reject_secret_like_env_names(settings: Settings, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        docker_run_args(default_policy(settings), "i", tmp_path, "a", env={"OPENAI_API_KEY": "x"})


@pytest.mark.parametrize(
    "command",
    [
        "pip install requests",
        "python -m pip install x",
        "curl https://example.com",
        "wget http://x",
        "uv add httpx",
        "git clone https://github.com/x/y",
        "npm install left-pad",
    ],
)
def test_commands_that_need_network_are_denied(settings: Settings, command: str) -> None:
    denial = check_command(default_policy(settings), command)
    assert denial is not None
    assert denial.reason_code == "network"


@pytest.mark.parametrize(
    "command", ["pytest -q", "alembic upgrade head", "python -c 'print(1)'", "git status"]
)
def test_ordinary_commands_are_allowed(settings: Settings, command: str) -> None:
    assert check_command(default_policy(settings), command) is None


@pytest.mark.parametrize(
    ("output", "exit_code", "oom", "timed_out", "reason"),
    [
        ("socket.gaierror: Temporary failure in name resolution", 1, False, False, "network"),
        (
            "OSError: [Errno 30] Read-only file system: '/etc/x'",
            1,
            False,
            False,
            "write_outside_workspace",
        ),
        ("", 137, True, False, "memory"),
        ("bash: fork: Resource temporarily unavailable", 1, False, False, "pids"),
        ("", 124, False, True, "timeout"),
    ],
)
def test_output_patterns_map_to_denials(
    settings: Settings, output: str, exit_code: int, oom: bool, timed_out: bool, reason: str
) -> None:
    denial = detect_denial(default_policy(settings), output, exit_code, oom, timed_out)
    assert denial is not None
    assert denial.reason_code == reason


def test_clean_failure_is_not_a_denial(settings: Settings) -> None:
    assert detect_denial(default_policy(settings), "AssertionError", 1, False, False) is None


def test_render_policy_lists_the_limits(settings: Settings) -> None:
    text = render_policy(default_policy(settings))
    for word in (
        "network: none",
        "cpus: 1.0",
        "memory: 1024 MB",
        "pids: 256",
        "user: 1000:1000",
        "read-only root: yes",
        "tool timeout: 120 s",
    ):
        assert word in text


class FakeRunner:
    def __init__(self, results: dict[str, subprocess.CompletedProcess[str]]) -> None:
        self.results = results
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        verb = argv[1]
        return self.results.get(verb, subprocess.CompletedProcess(argv, 0, "", ""))


def test_docker_exec_wraps_command_in_timeout_and_emits_start(
    settings: Settings, tmp_path: Path
) -> None:
    runner = FakeRunner({"run": subprocess.CompletedProcess([], 0, "abc123\n", "")})
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        sandbox = DockerSandbox(
            default_policy(settings), "img:1", tmp_path, bus, "r-1", "bare", runner=runner
        )
        assert sandbox.start() == "abc123"
        result = sandbox.exec("pytest -q", timeout_s=30)
    assert result.exit_code == 0
    exec_argv = runner.calls[1]
    assert exec_argv[:3] == ["docker", "exec", sandbox.name]
    assert "timeout" in exec_argv and "30" in exec_argv
    assert exec_argv[-3:] == ["bash", "-c", "pytest -q"]
    [start] = [e for e in read_events(log) if e.type == "sandbox_start"]
    assert start.data["network"] == "none"
    assert start.data["unsandboxed"] is False


def test_docker_exec_denied_command_never_runs(settings: Settings, tmp_path: Path) -> None:
    runner = FakeRunner({"run": subprocess.CompletedProcess([], 0, "abc\n", "")})
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        sandbox = DockerSandbox(
            default_policy(settings), "img:1", tmp_path, bus, "r-1", "bare", runner=runner
        )
        sandbox.start()
        result = sandbox.exec("pip install requests", timeout_s=30)
    assert result.denied is not None
    assert all(argv[1] != "exec" for argv in runner.calls)
    denied = [e for e in read_events(log) if e.type == "sandbox_denied"]
    assert denied[0].data["reason_code"] == "network"


def test_docker_usage_parses_stats(settings: Settings, tmp_path: Path) -> None:
    stats = {"CPUPerc": "12.50%", "MemUsage": "100MiB / 1GiB", "PIDs": "7"}
    runner = FakeRunner({"stats": subprocess.CompletedProcess([], 0, json.dumps(stats), "")})
    sandbox = DockerSandbox(
        default_policy(settings), "img:1", tmp_path, None, "r-1", "bare", runner=runner
    )
    usage = sandbox.usage()
    assert usage == {"cpu_pct": 12.5, "mem_mb": 100.0, "mem_limit_mb": 1024.0, "pids": 7}


def test_docker_exec_decodes_non_utf8_output_without_crashing(
    settings: Settings, tmp_path: Path
) -> None:
    class BytesRunner(FakeRunner):
        def __call__(self, argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
            self.calls.append(argv)
            if argv[1] == "exec":
                assert not kw.get("text"), "exec output must be read as bytes"
                return subprocess.CompletedProcess(argv, 0, bytes(range(256)), b"\xff\xfe")
            return subprocess.CompletedProcess(argv, 0, b"abc\n", b"")

    sandbox = DockerSandbox(
        default_policy(settings), "img:1", tmp_path, None, "r-1", "bare", runner=BytesRunner({})
    )
    sandbox.start()
    result = sandbox.exec("cat blob.bin", timeout_s=30)
    assert result.exit_code == 0
    assert "�" in result.output
    assert "xyz" in result.output  # the ASCII part of bytes(range(256)) survives decoding


def test_docker_exec_honours_a_harness_timeout_above_the_tool_cap(
    settings: Settings, tmp_path: Path
) -> None:
    runner = FakeRunner({})
    sandbox = DockerSandbox(
        default_policy(settings), "img:1", tmp_path, None, "r-1", "bare", runner=runner
    )
    sandbox.start()
    sandbox.exec("python -m shipharness.checks.runner", timeout_s=1200)
    exec_argv = next(argv for argv in runner.calls if argv[1] == "exec")
    assert exec_argv[exec_argv.index("--kill-after=5") + 1] == "1200"


def test_read_only_workspace_policy_mounts_work_read_only(
    settings: Settings, tmp_path: Path
) -> None:
    policy = default_policy(settings).model_copy(update={"workspace_read_only": True})
    args = docker_run_args(policy, "img:1", tmp_path, "c1")
    assert f"{tmp_path.resolve()}:/work:ro" in args
    default = docker_run_args(default_policy(settings), "img:1", tmp_path, "c1")
    assert f"{tmp_path.resolve()}:/work" in default  # arm containers keep a writable workspace
