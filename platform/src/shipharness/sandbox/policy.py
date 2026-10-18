"""Sandbox policy: identical machine-level limits for both arms."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from shipharness.config import Settings
from shipharness.sandbox.base import ReasonCode, SandboxDenial

_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET", re.IGNORECASE)
_CONTAINER_PATH = re.compile(r"^/[A-Za-z0-9._/-]+$")

Mount = tuple[Path, str, Literal["ro", "rw"]]  # (host path, container path, mode)


class DenyRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: str  # regex on the command
    reason_code: ReasonCode
    message: str  # shown to the agent


class DetectRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: str  # regex on combined output
    reason_code: ReasonCode


_NO_NETWORK = "the sandbox has no network; dependencies are already installed in the image"

DEFAULT_DENY_RULES: tuple[DenyRule, ...] = (
    DenyRule(pattern=r"\bpip3?\s+install\b", reason_code="network", message=_NO_NETWORK),
    DenyRule(pattern=r"\buv\s+(add|pip\s+install)\b", reason_code="network", message=_NO_NETWORK),
    DenyRule(pattern=r"\b(curl|wget)\b", reason_code="network", message=_NO_NETWORK),
    DenyRule(
        pattern=r"\bgit\s+(clone|fetch|pull|push)\b", reason_code="network", message=_NO_NETWORK
    ),
    DenyRule(
        pattern=r"\b(npm|yarn|pnpm)\s+(install|add)\b", reason_code="network", message=_NO_NETWORK
    ),
    DenyRule(pattern=r"\bapt(-get)?\s+install\b", reason_code="network", message=_NO_NETWORK),
)

DEFAULT_DETECT_RULES: tuple[DetectRule, ...] = (
    DetectRule(pattern=r"Temporary failure in name resolution", reason_code="network"),
    DetectRule(pattern=r"Name or service not known", reason_code="network"),
    DetectRule(pattern=r"Network is unreachable", reason_code="network"),
    DetectRule(pattern=r"Could not resolve host", reason_code="network"),
    DetectRule(pattern=r"Read-only file system", reason_code="write_outside_workspace"),
    DetectRule(pattern=r"fork: Resource temporarily unavailable", reason_code="pids"),
    DetectRule(pattern=r"can't start new thread", reason_code="pids"),
    DetectRule(pattern=r"\bMemoryError\b", reason_code="memory"),
)


# [walkthrough:S3:policy] start
class SandboxPolicy(BaseModel):
    """Machine-level limits. Identical for both arms in every run; never an A/B variable."""

    model_config = ConfigDict(frozen=True)

    version: int = 1
    network: str = "none"  # only loopback inside the container
    cpus: float = 1.0
    memory_mb: int = 1024
    swap_mb: int = 0  # --memory-swap equal to --memory: no swap
    pids_limit: int = 256
    user: str = "1000:1000"  # non-root
    read_only_root: bool = True  # writes only to /work (workspace) and /tmp
    tmpfs: dict[str, str] = {"/tmp": "rw,nosuid,size=256m"}
    cap_drop: tuple[str, ...] = ("ALL",)
    no_new_privileges: bool = True
    workspace_mount: str = "/work"
    workspace_read_only: bool = False  # True for board previews: they only read the arm
    tool_timeout_s: int = 120
    run_timeout_s: int = 300
    deny_command_patterns: tuple[DenyRule, ...] = DEFAULT_DENY_RULES
    detect_output_patterns: tuple[DetectRule, ...] = DEFAULT_DETECT_RULES


# [walkthrough:S3:policy] end


# [walkthrough:S3:run_args] start
def docker_run_args(
    policy: SandboxPolicy,
    image: str,
    workspace: Path,
    name: str,
    runtime: str = "docker",
    env: dict[str, str] | None = None,
    extra_mounts: list[Mount] | None = None,
) -> list[str]:
    """Full argv that starts one arm container. Never passes the host environment or keys."""
    args = [runtime, "run", "-d", "--rm", "--name", name, "--init"]
    args += ["--network", policy.network]
    mem = f"{policy.memory_mb}m"
    args += ["--memory", mem, "--memory-swap", f"{policy.memory_mb + policy.swap_mb}m"]
    args += ["--cpus", str(policy.cpus), "--pids-limit", str(policy.pids_limit)]
    if policy.read_only_root:
        args.append("--read-only")
    for mount, options in policy.tmpfs.items():
        args += ["--tmpfs", f"{mount}:{options}"]
    args += ["--user", policy.user]
    for cap in policy.cap_drop:
        args += ["--cap-drop", cap]
    if policy.no_new_privileges:
        args += ["--security-opt", "no-new-privileges"]
    for key, value in _container_env(env).items():
        args += ["-e", f"{key}={value}"]
    mode = ":ro" if policy.workspace_read_only else ""
    args += ["-v", f"{Path(workspace).resolve()}:{policy.workspace_mount}{mode}"]
    args += _mount_args(policy, extra_mounts)
    args += ["-w", policy.workspace_mount, image, "sleep", "infinity"]
    return args


# [walkthrough:S3:run_args] end


def _mount_args(policy: SandboxPolicy, mounts: list[Mount] | None) -> list[str]:
    """Extra bind mounts (the referee mounts hidden tests read-only). Never over the workspace."""
    args: list[str] = []
    for host, container, mode in mounts or []:
        if mode not in ("ro", "rw"):
            raise ValueError(f"mount mode must be 'ro' or 'rw', got {mode!r}")
        if not _CONTAINER_PATH.match(container) or ".." in container.split("/"):
            raise ValueError(f"container mount path must be absolute and plain: {container!r}")
        work, target = policy.workspace_mount.rstrip("/"), container.rstrip("/")
        if target == work or work.startswith(target + "/"):
            raise ValueError(f"extra mount {container!r} would shadow the workspace mount")
        if target.startswith(work + "/") and mode != "ro":
            raise ValueError(f"a mount inside the workspace must be read-only: {container!r}")
        args += ["-v", f"{Path(host).resolve()}:{container}:{mode}"]
    return args


def _container_env(extra: dict[str, str] | None) -> dict[str, str]:
    env = {"HOME": "/tmp/home", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    for key, value in (extra or {}).items():
        if _SECRET_NAME.search(key):
            raise ValueError(f"refusing to pass {key} into a container (secret-like name)")
        env[key] = value
    return env


def default_policy(settings: Settings) -> SandboxPolicy:
    """One policy for every container of a command (both arms, referee, previews)."""
    return SandboxPolicy(
        cpus=settings.sandbox_cpus,
        tool_timeout_s=settings.tool_timeout_s,
        run_timeout_s=settings.run_timeout_s,
    )


def check_command(policy: SandboxPolicy, command: str) -> SandboxDenial | None:
    """Pre-exec refusal for commands the sandbox cannot or must not run."""
    for rule in policy.deny_command_patterns:
        if re.search(rule.pattern, command):
            return SandboxDenial(reason_code=rule.reason_code, detail=rule.message, command=command)
    return None


def detect_denial(
    policy: SandboxPolicy, output: str, exit_code: int, oom_killed: bool, timed_out: bool
) -> SandboxDenial | None:
    """Post-exec classification of a sandbox limit hit."""
    if timed_out:
        return SandboxDenial(reason_code="timeout", detail="command exceeded its time limit")
    if oom_killed:
        return SandboxDenial(reason_code="memory", detail="process killed: memory limit")
    for rule in policy.detect_output_patterns:
        match = re.search(rule.pattern, output)
        if match:
            return SandboxDenial(reason_code=rule.reason_code, detail=match.group(0))
    return None


def render_policy(policy: SandboxPolicy) -> str:
    """Human-readable policy, printed at run start."""
    lines = [
        "Sandbox policy (identical for both arms)",
        f"  network: {policy.network}",
        f"  cpus: {policy.cpus}",
        f"  memory: {policy.memory_mb} MB (swap: {policy.swap_mb} MB)",
        f"  pids: {policy.pids_limit}",
        f"  user: {policy.user}",
        f"  read-only root: {'yes' if policy.read_only_root else 'no'}",
        f"  writable: {policy.workspace_mount}, " + ", ".join(policy.tmpfs),
        f"  capabilities dropped: {', '.join(policy.cap_drop)}",
        f"  tool timeout: {policy.tool_timeout_s} s; run timeout: {policy.run_timeout_s} s",
        f"  refused commands: {len(policy.deny_command_patterns)} rules (network access)",
    ]
    return "\n".join(lines)
