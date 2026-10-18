"""Shared fixtures for filter tests: a tiny trusted repo and a LocalSandbox on it."""

from __future__ import annotations

import sys
from pathlib import Path

from shipharness.config import Settings
from shipharness.sandbox import LocalSandbox, default_policy

PY = f'"{sys.executable}"'

CALC = """\
def add(a, b):
    return a + b


def sign(x):
    if x < 0:
        return -1
    if x == 0:
        return 0
    return 1


def clamp(x, low, high):
    if x < low:
        return low
    if x > high:
        return high
    return x
"""

EXISTING_TEST = """\
from calc import add, sign


def test_add():
    assert add(2, 3) == 5


def test_sign_negative():
    assert sign(-4) == -1
"""


def make_repo(root: Path) -> Path:
    """calc.py with partial coverage from tests/test_calc.py."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    (root / "calc.py").write_text(CALC, encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_calc.py").write_text(EXISTING_TEST, encoding="utf-8")
    return root


def local_sandbox(workspace: Path) -> LocalSandbox:
    sandbox = LocalSandbox(
        default_policy(Settings(_env_file=None)), workspace, None, "r-test", "bare"
    )
    sandbox.start()
    return sandbox


MATHX = '''\
def double(x):
    """Twice x.

    >>> double(4)
    8
    """
    return x * 2


def triple(x):
    return x * 3
'''

MATHX_TEST = """\
from mathx import triple


def test_triple():
    assert triple(2) == 6
"""

DOUBLE_TEST = """\
from mathx import double


def test_double():
    assert double(5) == 10
"""


def make_doctest_repo(root: Path) -> Path:
    """mathx.py: `double` is covered only by its doctest, `triple` by tests/test_mathx.py."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    (root / "mathx.py").write_text(MATHX, encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_mathx.py").write_text(MATHX_TEST, encoding="utf-8")
    return root
