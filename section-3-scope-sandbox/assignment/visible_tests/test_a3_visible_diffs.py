"""Visible tests: diff parsing, path matching, and the per-phase diff-scope policy.

Test name prefixes map to the grading criteria (README): test_parse_* (diff parsing and path
matching), test_bad_* (out-of-scope diffs rejected), test_good_* (legitimate diffs accepted).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from a3_checks import assert_accepted, assert_changed_paths, assert_rejected, load_cases

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CASES = load_cases(FIXTURES)
BAD = [c for c in CASES if c["kind"] == "bad"]
GOOD = [c for c in CASES if c["kind"] == "good"]
WITH_PATHS = [c for c in CASES if "changed" in c]


@pytest.mark.parametrize("case", WITH_PATHS, ids=[c["id"] for c in WITH_PATHS])
def test_parse_changed_paths(case) -> None:  # type: ignore[no-untyped-def]
    assert_changed_paths(case)


@pytest.mark.parametrize("case", BAD, ids=[c["id"] for c in BAD])
def test_bad_diff_rejected(case) -> None:  # type: ignore[no-untyped-def]
    assert_rejected(case)


@pytest.mark.parametrize("case", GOOD, ids=[c["id"] for c in GOOD])
def test_good_diff_accepted(case) -> None:  # type: ignore[no-untyped-def]
    assert_accepted(case)


# -- parse_diff details ---------------------------------------------------------------------------


def test_parse_statuses_of_a_rename_and_a_new_file() -> None:
    from a3scope.diffparse import FileChange, parse_diff

    diff = (FIXTURES / "diffs" / "bad-rename-out-of-scope.diff").read_bytes()
    assert parse_diff(diff) == [
        FileChange(old_path="app/api/issues.py", new_path="app/api/issues_v2.py", status="renamed")
    ]
    diff = (FIXTURES / "diffs" / "bad-middleware-file.diff").read_bytes()
    added = parse_diff(diff)[1]
    assert (added.old_path, added.new_path, added.status) == (
        None,
        "app/middleware/idempotency.py",
        "added",
    )


def test_parse_binary_flag_and_space_in_path() -> None:
    from a3scope.diffparse import parse_diff

    (change,) = parse_diff((FIXTURES / "diffs" / "bad-binary-out-of-scope.diff").read_bytes())
    assert change.binary is True and change.status == "modified"
    (change,) = parse_diff((FIXTURES / "diffs" / "good-space-in-path.diff").read_bytes())
    assert change.new_path == "docs/design notes/f3 retry.md"  # no trailing tab
    assert change.binary is False


def test_parse_accepts_str_and_bytes() -> None:
    from a3scope.diffparse import parse_diff

    raw = (FIXTURES / "diffs" / "good-in-scope-build.diff").read_bytes()
    assert parse_diff(raw) == parse_diff(raw.decode("utf-8"))


def test_parse_copy_source_is_read_not_changed() -> None:
    from a3scope.diffparse import changed_paths, parse_diff

    changes = parse_diff((FIXTURES / "diffs" / "good-copy-from-out-of-scope.diff").read_bytes())
    assert [c.status for c in changes] == ["copied"]
    assert changes[0].old_path == "app/core/config.py"
    assert changed_paths(changes) == ["tests/visible/config_snapshot.py"]


def test_parse_hunks_without_a_file_header_raise() -> None:
    from a3scope.diffparse import DiffParseError, parse_diff

    with pytest.raises(DiffParseError):
        parse_diff("@@ -1 +1 @@\n-a\n+b\n")


# -- glob semantics (same as src/shipharness/harness/scope/guard.py) -------------------------------


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("tests/visible/test_a.py", "tests/visible/**", True),
        ("tests/visible/api/v2/test_a.py", "tests/visible/**", True),
        ("tests/visible", "tests/visible/**", False),
        ("app/api/issues.py", "app/api/issues.py", True),
        ("app/api/issues.py", "app/*/issues.py", True),
        ("app/api/v2/issues.py", "app/*/issues.py", False),
        ("docs/x.md", "docs/**/*.md", True),
        ("docs/a/b/x.md", "docs/**/*.md", True),
        ("app/api/issue.py", "app/api/issue?.py", False),
        ("app/api/issues.py", "app/api/issue?.py", True),
        ("app/api/issues+py", "app/api/issues.py", False),
    ],
)
def test_parse_glob_matches(path: str, pattern: str, expected: bool) -> None:
    from a3scope.scope import glob_matches

    assert glob_matches(path, pattern) is expected


# -- check_diff details ----------------------------------------------------------------------------


def test_bad_refusal_order_and_one_refusal_per_path() -> None:
    from a3scope.scope import PhasePolicy, check_diff

    diff = (FIXTURES / "diffs" / "bad-middleware-file.diff").read_bytes()
    policy = PhasePolicy(allowed_paths={"build": ["docs/**"]})
    verdict = check_diff(policy, "build", diff)
    assert [r.path for r in verdict.refusals] == [
        "app/api/issues.py",
        "app/middleware/idempotency.py",
    ]
    assert verdict.phase == "build"


def test_bad_harness_only_wins_over_an_allow_list_that_matches() -> None:
    from a3scope.scope import PhasePolicy, check_diff

    diff = (FIXTURES / "diffs" / "bad-feature-list-edit.diff").read_bytes()
    verdict = check_diff(PhasePolicy(allowed_paths={"build": ["*.json"]}), "build", diff)
    assert [(r.path, r.code) for r in verdict.refusals] == [("feature_list.json", "harness_only")]
