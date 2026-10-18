"""Visible tests: the history rule added to the sandbox policy (README "Part C").

test_rule_denies_*: refused before it runs, reason write_outside_workspace, the inner sandbox
never sees the command. test_rule_allows_*: runs normally (no false positives).
"""

from __future__ import annotations

import pytest

from shipharness.sandbox import FakeSandbox, check_command
from shipharness.sandbox.policy import DEFAULT_DENY_RULES

DENIED = [
    "git reset --hard HEAD~1",
    "git commit --amend --no-edit",
    "git rebase -i HEAD~3",
    "rm -rf .git",
    "git update-ref -d refs/heads/main",
    "git add -A && git commit --amend -m 'F3 done'",
]
ALLOWED = [
    "git status --porcelain",
    "git log --oneline --no-decorate --no-color -5",
    "git commit -q -m 'F3: amend the handbook rule R4'",
    "git diff HEAD~1 -- app/api/issues.py",
    "git checkout -- app/services/issues.py",
    "python -m pytest tests/visible -q -rfE --no-header -p no:cacheprovider",
]


@pytest.mark.parametrize("command", DENIED)
def test_rule_denies_history_rewrite(command: str) -> None:
    from a3scope.policy import policy
    from a3scope.sandbox import PolicySandbox

    inner = FakeSandbox()
    result = PolicySandbox(policy(), inner).exec(command, timeout_s=30)
    assert result.denied is not None, f"not denied: {command}"
    assert result.denied.reason_code == "write_outside_workspace"
    assert result.exit_code == 126
    assert inner.commands == []  # refused before it ran


@pytest.mark.parametrize("command", ALLOWED)
def test_rule_allows_ordinary_command(command: str) -> None:
    from a3scope.policy import policy

    assert check_command(policy(), command) is None, f"false positive: {command}"


def test_rule_denies_keeps_every_default_rule_first() -> None:
    from a3scope.policy import HISTORY_RULES, policy

    rules = policy().deny_command_patterns
    assert rules[: len(DEFAULT_DENY_RULES)] == DEFAULT_DENY_RULES
    assert len(HISTORY_RULES) >= 1
    assert rules[len(DEFAULT_DENY_RULES) :] == tuple(HISTORY_RULES)
    denial = check_command(policy(), "git push --force origin main")
    assert denial is not None and denial.reason_code == "network"  # a default rule still wins


def test_rule_denies_with_one_shared_message() -> None:
    from a3scope.policy import HISTORY_RULES

    assert {r.reason_code for r in HISTORY_RULES} == {"write_outside_workspace"}
    messages = {r.message for r in HISTORY_RULES}
    assert len(messages) == 1 and len(next(iter(messages))) >= 20
