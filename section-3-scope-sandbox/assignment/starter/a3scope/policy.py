"""Part C: one sandbox policy rule, "git history in the workspace is append-only".

The scope guard's byte snapshot skips `.git` (src/shipharness/harness/scope/snapshot.py), so a
history rewrite can never be reverted, and `passes` evidence names a commit SHA that a rewrite
would orphan. This rule refuses such commands before they run, the way the default rules in
src/shipharness/sandbox/policy.py refuse network commands. README "Detailed requirements,
Part C" lists what must be denied and what must keep running.
"""

from __future__ import annotations

from shipharness.sandbox.policy import DEFAULT_DENY_RULES, DenyRule, SandboxPolicy

# TODO(A3 Part C): one shared message for every pattern of the rule (at least 20 characters):
# say what was refused and what to do instead.
HISTORY_MESSAGE = ""

# TODO(A3 Part C): the rule, as one or more DenyRule patterns (regex on the command) that share
# reason_code="write_outside_workspace" and HISTORY_MESSAGE.
HISTORY_RULES: tuple[DenyRule, ...] = ()


def policy() -> SandboxPolicy:
    """The default policy plus the history rule, defaults first. Reads HISTORY_RULES at call
    time (the grader removes the rule to check that your denial test notices)."""
    return SandboxPolicy(deny_command_patterns=(*DEFAULT_DENY_RULES, *HISTORY_RULES))
