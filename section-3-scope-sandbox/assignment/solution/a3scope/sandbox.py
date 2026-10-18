"""Given (no TODO): a sandbox wrapper that applies a policy's deny rules before running.

PolicySandbox.exec does what the first lines of DockerSandbox.exec do
(src/shipharness/sandbox/docker.py): call check_command, and on a denial return exit code 126
with "DENIED by sandbox: <message>" without running anything. Wrap a FakeSandbox to test a rule
with no container; wrap a DockerSandbox, or pass your policy to DockerSandbox itself, to test it
in a real container (pytest -m docker).
"""

from __future__ import annotations

from shipharness.sandbox import ExecResult, Sandbox, SandboxPolicy, check_command


class PolicySandbox:
    def __init__(self, policy: SandboxPolicy, inner: Sandbox) -> None:
        self.policy = policy
        self.inner = inner
        self.denials: list[str] = []

    def start(self) -> str:
        return self.inner.start()

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        denial = check_command(self.policy, command)
        if denial is not None:
            self.denials.append(command)
            return ExecResult(
                exit_code=126,
                output=f"DENIED by sandbox: {denial.detail}",
                duration_ms=0,
                denied=denial,
            )
        return self.inner.exec(command, timeout_s)

    def usage(self) -> dict[str, float]:
        return self.inner.usage()

    def stop(self) -> None:
        self.inner.stop()
