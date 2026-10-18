"""Your denial test for the history rule (README task 6).

Requirements (the grader checks all three):
1. Every test here passes with your rule in place.
2. At least one test fails when the rule is removed (the grader empties HISTORY_RULES).
3. The denial is proved through the real policy code: use shipharness.sandbox.check_command
   or a3scope.sandbox.PolicySandbox around a FakeSandbox, with a3scope.policy.policy().

Run (from the repository root):
    uv run python -m pytest -q -p no:cacheprovider \
        section-3-scope-sandbox/assignment/starter/tests
"""

from __future__ import annotations

import pytest


def test_history_rewrite_is_denied_before_it_runs() -> None:
    # TODO(A3 task 6): wrap a FakeSandbox in PolicySandbox(policy(), inner), exec a command
    # that rewrites history, and assert the denial: reason code, exit code 126, and that the
    # inner sandbox never received the command. Add a test for a command that must still run.
    pytest.fail("TODO(A3 task 6): write the denial test")
