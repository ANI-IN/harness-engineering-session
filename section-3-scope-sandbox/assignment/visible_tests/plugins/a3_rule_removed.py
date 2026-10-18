"""pytest plugin (-p a3_rule_removed): run a test session with the history rule removed.

Used by check.py and the grader to confirm that the learner's denial test notices a missing
rule: HISTORY_RULES becomes empty and policy() returns the default policy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    impl = os.environ.get("A3_IMPL")
    if impl and str(Path(impl).resolve()) not in sys.path:
        sys.path.insert(0, str(Path(impl).resolve()))
    import a3scope.policy as module

    from shipharness.sandbox.policy import SandboxPolicy

    module.HISTORY_RULES = ()
    module.policy = lambda: SandboxPolicy()
