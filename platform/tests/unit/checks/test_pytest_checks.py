"""regression, hidden_tests, flakiness: pytest runs in a child process inside the build."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from shipharness.checks import CheckContext, CheckResult, get_check
from shipharness.checks.builtin import load_builtin_checks
from tests.unit.checks.seeds import edit

load_builtin_checks()

HIDDEN = """\
from conftest import auth


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_feature_that_is_not_built(client, acme):
    assert client.get("/issues/1/comments", headers=auth(acme.admin)).status_code == 200
"""

FLAKY = """\
from pathlib import Path

COUNTER = Path(__file__).with_name("counter.txt")


def test_stable():
    assert True


def test_flaky():
    n = int(COUNTER.read_text()) if COUNTER.exists() else 0
    COUNTER.write_text(str(n + 1))
    assert n % 2 == 0


def test_always_fails():
    assert False
"""


def run(name: str, build: Path, **params: object) -> CheckResult:
    ctx = CheckContext(checkpoint="m1-base", feature_id="F1", params=dict(params))
    return get_check(name).run(build, ctx)


def failed_ids(result: CheckResult) -> set[str]:
    return {f.detail_key for f in result.findings if f.counted}


def test_regression_base_keeps_every_visible_test_passing(base_build: Path) -> None:
    result = run("regression", base_build)
    assert result.passed is True, result.findings[:3]
    assert result.total_probes >= 100


def test_regression_catches_a_broken_behaviour(make_build: Callable[[], Path]) -> None:
    build = make_build()
    edit(build, "app/api/errors.py", '    404: "not_found",', '    404: "missing",')
    edit(build, "app/services/errors.py", '    code = "not_found"', '    code = "missing"')
    result = run("regression", build, regression_targets=["tests/visible/test_tenant_isolation.py"])
    assert result.passed is False
    assert all(
        key.startswith("test:tests/visible/test_tenant_isolation.py::")
        for key in failed_ids(result)
    )


def test_hidden_tests_count_passed_and_failed(make_build: Callable[[], Path]) -> None:
    build = make_build()
    (build / "tests" / "hidden").mkdir()
    (build / "tests" / "hidden" / "test_f9.py").write_text(HIDDEN, encoding="utf-8")
    (build / "tests" / "hidden" / "conftest.py").write_text(
        "from tests.visible.conftest import *  # noqa: F403\n", encoding="utf-8"
    )
    ids = [
        "tests/hidden/test_f9.py::test_health_is_public",
        "tests/hidden/test_f9.py::test_feature_that_is_not_built",
        "tests/hidden/test_f9.py::test_missing",
    ]
    result = run("hidden_tests", build, hidden_tests=ids)
    assert result.total_probes == 3
    assert failed_ids(result) == {f"test:{ids[1]}", f"test:{ids[2]}"}
    missing = next(f for f in result.findings if f.detail_key == f"test:{ids[2]}")
    assert "not collected" in missing.detail


def test_hidden_tests_without_ids_is_an_error(base_build: Path) -> None:
    result = run("hidden_tests", base_build)
    assert result.passed is False
    assert result.findings[0].severity == "error"


def test_flakiness_finds_tests_that_pass_and_fail(make_build: Callable[[], Path]) -> None:
    build = make_build()
    (build / "tests" / "visible" / "test_shipped.py").write_text(FLAKY, encoding="utf-8")
    result = run("flakiness", build, shipped_tests=["tests/visible/test_shipped.py"], flaky_runs=3)
    assert failed_ids(result) == {"test:tests/visible/test_shipped.py::test_flaky"}
    assert result.total_probes == 3
    always = [f for f in result.findings if not f.counted]
    assert [f.detail_key for f in always] == [
        "test:tests/visible/test_shipped.py::test_always_fails"
    ]


def test_flakiness_runs_shipped_tests_five_times_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shipharness.checks.pytest_checks as module

    runs: list[list[str]] = []

    def fake_run(build: Path, targets: list[str], *args: object, **kwargs: object) -> object:
        runs.append(list(targets))
        return SimpleNamespace(outcomes={"tests/visible/test_a.py::test_a": "passed"})

    monkeypatch.setattr(module, "run_pytest", fake_run)
    result = run("flakiness", tmp_path, shipped_tests=["tests/visible/test_a.py"])
    assert len(runs) == 5  # TestGen-LLM's five executions (B11)
    assert result.passed is True and result.total_probes == 1


def test_flakiness_with_no_shipped_tests_passes(base_build: Path) -> None:
    result = run("flakiness", base_build, shipped_tests=[])
    assert result.passed is True
    assert result.total_probes == 0


def test_regression_reports_an_existing_test_the_arm_removed(tmp_path: Path) -> None:
    visible = tmp_path / "tests" / "visible"
    visible.mkdir(parents=True)
    (visible / "test_a.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")
    expected = ["tests/visible/test_a.py::test_one", "tests/visible/test_a.py::test_two"]
    result = run("regression", tmp_path, regression_expected=expected)
    assert failed_ids(result) == {"test:tests/visible/test_a.py::test_two"}
    assert "removed or renamed" in result.findings[0].detail


def test_regression_matches_parametrized_ids_by_their_base_name(tmp_path: Path) -> None:
    visible = tmp_path / "tests" / "visible"
    visible.mkdir(parents=True)
    (visible / "test_a.py").write_text(
        "import pytest\n\n\n@pytest.mark.parametrize('x', [1, 2])\ndef test_p(x):\n    assert x\n",
        encoding="utf-8",
    )
    result = run("regression", tmp_path, regression_expected=["tests/visible/test_a.py::test_p"])
    assert result.passed is True


CHECKPOINT_TESTS = """\
import pytest


def test_one():
    assert True


@pytest.mark.parametrize("x", [1, 2])
def test_p(x):
    assert x


class TestK:
    def test_m(self):
        assert True
"""
CHECKPOINT_IDS = [
    "tests/visible/test_a.py::test_one",
    "tests/visible/test_a.py::test_p",
    "tests/visible/test_a.py::TestK::test_m",
    "tests/visible/test_b.py::test_b",
]


def _checkpoint(root: Path) -> Path:
    visible = root / "tests" / "visible"
    visible.mkdir(parents=True)
    (visible / "test_a.py").write_text(CHECKPOINT_TESTS, encoding="utf-8")
    (visible / "test_b.py").write_text("def test_b():\n    assert True\n", encoding="utf-8")
    return root


def _regression_on_ids(build: Path) -> CheckResult:
    return run(
        "regression", build, regression_targets=CHECKPOINT_IDS, regression_expected=CHECKPOINT_IDS
    )


def test_regression_on_checkpoint_ids_ignores_tests_the_arm_added(tmp_path: Path) -> None:
    checkpoint = _regression_on_ids(_checkpoint(tmp_path / "checkpoint"))
    assert checkpoint.passed is True and checkpoint.total_probes == 5  # test_p runs both params
    build = _checkpoint(tmp_path / "arm")
    with (build / "tests" / "visible" / "test_a.py").open("a", encoding="utf-8") as fh:
        fh.write("\n\ndef test_added_by_the_arm():\n    assert False\n")
    (build / "tests" / "visible" / "test_new.py").write_text(
        "def test_new():\n    assert False\n", encoding="utf-8"
    )
    result = _regression_on_ids(build)
    assert result.passed is True, result.findings
    assert result.total_probes == checkpoint.total_probes


def test_regression_on_checkpoint_ids_reports_removed_tests_and_runs_the_rest(
    tmp_path: Path,
) -> None:
    build = _checkpoint(tmp_path)
    edited = CHECKPOINT_TESTS.replace("def test_one():", "def test_renamed():")
    (build / "tests" / "visible" / "test_a.py").write_text(edited, encoding="utf-8")
    (build / "tests" / "visible" / "test_b.py").unlink()
    result = _regression_on_ids(build)
    assert failed_ids(result) == {
        "test:tests/visible/test_a.py::test_one",
        "test:tests/visible/test_b.py::test_b",
    }
    assert all("removed or renamed" in f.detail for f in result.findings)
    assert result.total_probes == 5  # three still run, two missing
