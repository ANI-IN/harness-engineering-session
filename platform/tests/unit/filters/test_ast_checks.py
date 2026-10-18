from __future__ import annotations

import pytest

from shipharness.filters.ast_checks import check_test

MODULE = """\
from helpers import fetch_rate


def add(a, b):
    return a + b


class Account:
    def deposit(self, amount):
        return amount


LIMIT = 10
"""


def check(source: str, name: str = "test_it", target: str | None = "calc") -> tuple[bool, str]:
    return check_test(source, f"tests/test_x.py::{name}", target, MODULE)


@pytest.mark.parametrize(
    "body",
    [
        "    assert add(1, 2) == 3\n",
        "    with pytest.raises(ValueError):\n        add(None, 1)\n",
        "    self_check(add(1, 2))\n",
        "    result = add(1, 2)\n    assert result\n",
    ],
)
def test_real_assertions_pass(body: str) -> None:
    source = (
        "import pytest\nfrom calc import add\n\n\n"
        "def self_check(value):\n    assert value == 3\n\n\n"
        f"def test_it():\n{body}"
    )
    ok, reason = check(source)
    assert ok, reason


@pytest.mark.parametrize(
    "body",
    [
        "    add(1, 2)\n",
        "    assert True\n",
        "    assert 1\n",
        "    assert True is not False\n",
        "    x = add(1, 2)\n    assert x == x\n",
    ],
)
def test_missing_or_vacuous_assertions_are_discarded(body: str) -> None:
    ok, reason = check(f"from calc import add\n\n\ndef test_it():\n{body}")
    assert not ok
    assert reason.startswith("no real assertion")


def test_method_in_class_and_parametrized_id() -> None:
    source = "class TestCalc:\n    def test_add(self, n):\n        assert n + 1 > n\n"
    ok, reason = check_test(source, "tests/test_x.py::TestCalc::test_add[3]", None, None)
    assert ok, reason
    assert "mocking not checked" in reason


def test_unknown_function_and_syntax_error() -> None:
    assert check("def test_other():\n    assert 1 == 2\n")[1].startswith("test function test_it")
    ok, reason = check("def test_it(:\n")
    assert not ok
    assert "does not parse" in reason


MOCKING = [
    'from unittest.mock import patch\n\n\n@patch("calc.add")\n'
    "def test_it(fake):\n    assert fake(1, 2)\n",
    "import calc\n\n\ndef test_it(monkeypatch):\n"
    '    monkeypatch.setattr(calc, "add", lambda a, b: 3)\n    assert calc.add(1, 2) == 3\n',
    "import calc\n\n\ndef test_it(monkeypatch):\n"
    '    monkeypatch.setattr("calc.add", lambda a, b: 3)\n    assert calc.add(1, 2) == 3\n',
    "import calc as c\n\n\ndef test_it(mocker):\n"
    '    mocker.patch.object(c, "Account")\n    assert c.add(1, 2) == 3\n',
    "from calc import Account\n\n\ndef test_it(monkeypatch):\n"
    '    monkeypatch.setattr(Account, "deposit", lambda s, a: 0)\n'
    "    assert Account().deposit(5) == 0\n",
    "import calc\n\n\ndef test_it():\n"
    "    calc.add = lambda a, b: 0\n    assert calc.add(1, 1) == 0\n",
    "import calc\nfrom unittest import mock\n\n\ndef test_it():\n"
    '    with mock.patch("calc"):\n        assert calc.add(1, 1) == 2\n',
]


@pytest.mark.parametrize("source", MOCKING)
def test_mocking_the_unit_under_test_is_discarded(source: str) -> None:
    ok, reason = check(source)
    assert not ok
    assert reason.startswith("mocks the unit under test (calc)")


def test_mocking_in_a_requested_fixture_is_discarded() -> None:
    source = (
        "import pytest\nimport calc\n\n\n@pytest.fixture\ndef fake(monkeypatch):\n"
        '    monkeypatch.setattr(calc, "add", lambda a, b: 0)\n\n\n'
        "def test_it(fake):\n    assert calc.add(1, 2) == 0\n"
    )
    ok, reason = check(source)
    assert not ok
    assert "mocks the unit under test" in reason


def test_patching_a_dependency_of_the_unit_is_allowed() -> None:
    source = (
        "from unittest.mock import patch\nimport calc\n\n\n"
        "def test_it():\n"
        '    with patch("calc.fetch_rate", return_value=2):\n'
        "        assert calc.add(1, 2) == 3\n"
    )
    ok, reason = check(source)
    assert ok, reason
