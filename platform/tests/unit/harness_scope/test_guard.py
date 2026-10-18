"""Allowed-path globs and apply_patch target parsing."""

from __future__ import annotations

import pytest

from shipharness.harness.scope.guard import (
    FEATURE_LIST_REASON,
    PathRules,
    glob_matches,
    patch_targets,
)


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("app/api/issues.py", "app/api/issues.py", True),
        ("app/api/projects.py", "app/api/issues.py", False),
        ("tests/visible/test_a.py", "tests/visible/**", True),
        ("tests/visible/sub/dir/test_b.py", "tests/visible/**", True),
        ("tests/visible_extra/test_a.py", "tests/visible/**", False),
        ("tests/hidden2/x.py", "tests/visible/**", False),
        ("app/services/issues.py", "app/services/*.py", True),
        ("app/services/sub/issues.py", "app/services/*.py", False),
        ("app/services/issues.pyc", "app/services/*.py", False),
        ("docs/a/b/c.md", "docs/**/c.md", True),
        ("docs/c.md", "docs/**/c.md", True),
        ("app/x1.py", "app/x?.py", True),
        ("app/a.py", "app?a.py", False),  # '?' never matches '/'
        ("appxpy", "app.py", False),  # '.' is literal
    ],
)
def test_glob_matches(path: str, pattern: str, expected: bool) -> None:
    assert glob_matches(path, pattern) is expected


def rules(phase: str = "build", state_files: bool = True) -> PathRules:
    allowed = {"build": ["app/api/issues.py", "tests/visible/**"], "test": ["tests/visible/**"]}
    return PathRules(phase=phase, allowed=allowed.get(phase), state_files=state_files)


def test_allowed_path_has_no_reason() -> None:
    assert rules().reason("app/api/issues.py") is None
    assert rules().reason("./tests/visible/test_new.py") is None


def test_out_of_scope_reason_names_the_path_phase_and_list() -> None:
    reason = rules().reason("app/models.py")
    assert reason is not None
    assert "app/models.py" in reason and "build phase" in reason
    assert "app/api/issues.py" in reason


def test_test_phase_uses_its_own_list() -> None:
    assert rules("test").reason("app/api/issues.py") is not None
    assert rules("test").reason("tests/visible/test_x.py") is None


def test_feature_list_is_never_allowed() -> None:
    assert rules().reason("feature_list.json") == FEATURE_LIST_REASON
    assert FEATURE_LIST_REASON == "feature_list.json is written only by the harness"
    assert rules().reason("feature_list.schema.json") is not None
    open_rules = PathRules(phase="build", allowed=None, state_files=True)
    assert open_rules.reason("feature_list.json") == FEATURE_LIST_REASON


def test_state_files_are_allowed_only_with_the_state_layer() -> None:
    for path in ("progress.md", "session-handoff.md", "docs/exec-plans/active/F3.md"):
        assert rules(state_files=True).reason(path) is None
        assert rules(state_files=False).reason(path) is not None
    assert rules(state_files=True).reason("init.sh") is not None


def test_no_allow_list_means_no_path_restriction() -> None:
    assert PathRules(phase="build", allowed=None, state_files=False).reason("anything.py") is None


def test_patch_targets_reads_headers_renames_and_copies() -> None:
    patch = (
        "diff --git a/app/api/issues.py b/app/api/issues.py\n"
        "--- a/app/api/issues.py\n+++ b/app/api/issues.py\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/app/old.py b/app/new.py\nsimilarity index 100%\n"
        "rename from app/old.py\nrename to app/new.py\n"
        "diff --git a/x.py b/y.py\ncopy from x.py\ncopy to y.py\n"
        "--- /dev/null\n+++ b/tests/visible/test_new.py\n@@ -0,0 +1 @@\n+x\n"
    )
    assert patch_targets(patch) == [
        "app/api/issues.py",
        "app/old.py",
        "app/new.py",
        "x.py",
        "y.py",
        "tests/visible/test_new.py",
    ]


def test_patch_targets_without_prefixes() -> None:
    patch = "--- app/api/issues.py\n+++ app/api/issues.py\n@@ -1 +1 @@\n-a\n+b\n"
    assert patch_targets(patch) == ["app/api/issues.py"]
