"""Reference denial test for the history rule (README task 6).

Each denial goes through the real policy code: policy() from a3scope.policy, check_command from
shipharness.sandbox, and PolicySandbox around a FakeSandbox, which proves the command never
reached the sandbox.
"""

from __future__ import annotations

import pytest
from a3scope.policy import HISTORY_MESSAGE, policy
from a3scope.sandbox import PolicySandbox

from shipharness.sandbox import FakeSandbox, check_command


@pytest.mark.parametrize(
    "command",
    [
        "git reset --hard HEAD~1",
        "git -c user.name=agent commit --amend --no-edit",
        "git rebase -i HEAD~2",
        "rm -rf .git",
    ],
)
def test_history_rewrite_is_denied_before_it_runs(command: str) -> None:
    inner = FakeSandbox()
    box = PolicySandbox(policy(), inner)
    result = box.exec(command, timeout_s=30)
    assert result.denied is not None
    assert result.denied.reason_code == "write_outside_workspace"
    assert result.exit_code == 126
    assert result.output == f"DENIED by sandbox: {HISTORY_MESSAGE}"
    assert inner.commands == []
    assert box.denials == [command]


@pytest.mark.parametrize(
    "command",
    [
        "git revert --no-edit HEAD",
        "git commit -q -m 'amend the handbook'",
        "git reset HEAD app/api/issues.py",
        'grep -rn "git rebase" docs/',
    ],
)
def test_append_only_commands_still_run(command: str) -> None:
    inner = FakeSandbox()
    result = PolicySandbox(policy(), inner).exec(command, timeout_s=30)
    assert result.denied is None
    assert inner.commands == [command]


def test_without_the_rule_the_default_policy_lets_a_rewrite_through() -> None:
    from shipharness.sandbox import SandboxPolicy

    assert check_command(SandboxPolicy(), "git reset --hard HEAD~1") is None
    assert check_command(policy(), "git reset --hard HEAD~1") is not None
