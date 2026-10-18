from __future__ import annotations

from collections.abc import Callable

from shipharness.harness.verify.clean_state import clean_state_check
from shipharness.sandbox import ExecResult, FakeSandbox

from .fakes import fail, ok

BASE = "a" * 40
DIFF_PRINT = """diff --git a/app/api/x.py b/app/api/x.py
--- a/app/api/x.py
+++ b/app/api/x.py
@@ -1,0 +2,2 @@
+    print("debug", items)
+    return items
"""


def scripted(**overrides: ExecResult) -> Callable[[str], ExecResult]:
    defaults = {
        "status": ok(""),
        "names": ok(""),
        "ruff": ok(""),
        "heads": ok("abc123 (head)\n"),
        "diff": ok(""),
    }
    defaults.update(overrides)

    def script(command: str) -> ExecResult:
        if command.startswith("git status"):
            return defaults["status"]
        if command.startswith("git diff --name-only"):
            return defaults["names"]
        if command.startswith("ruff"):
            return defaults["ruff"]
        if command.startswith("alembic"):
            return defaults["heads"]
        if command.startswith("git diff -U0"):
            return defaults["diff"]
        raise AssertionError(f"unexpected command {command}")

    return script


def test_clean_workspace_passes() -> None:
    item = clean_state_check(FakeSandbox(scripted()), BASE)
    assert item.name == "clean state"
    assert item.status == "pass"


def test_uncommitted_changes_fail_but_generated_files_are_ignored() -> None:
    status = ok("?? app/new.py\n M app/main.py\n?? .pytest_cache/v/x\n?? app/__pycache__/a.pyc\n")
    item = clean_state_check(FakeSandbox(scripted(status=status)), BASE)
    assert item.status == "fail"
    assert "uncommitted changes: app/new.py, app/main.py" in item.detail
    assert "pytest_cache" not in item.detail


def test_ruff_problems_in_changed_files_fail() -> None:
    sandbox = FakeSandbox(
        scripted(
            names=ok("app/api/x.py\n"),
            ruff=fail("app/api/x.py:3:1: F401 `os` imported but unused\nFound 1 error.\n"),
        )
    )
    item = clean_state_check(sandbox, BASE)
    assert item.status == "fail"
    assert "ruff" in item.detail and "F401" in item.detail
    assert any(c.startswith("ruff check") and "app/api/x.py" in c for c in sandbox.commands)


def test_ruff_is_not_run_when_no_python_file_changed() -> None:
    sandbox = FakeSandbox(scripted())
    clean_state_check(sandbox, BASE)
    assert not any(c.startswith("ruff") for c in sandbox.commands)


def test_two_migration_heads_fail() -> None:
    heads = ok("abc123 (head)\ndef456 (head)\n")
    item = clean_state_check(FakeSandbox(scripted(heads=heads)), BASE)
    assert item.status == "fail"
    assert "migration heads: 2" in item.detail


def test_added_print_in_source_fails_as_debug_output() -> None:
    item = clean_state_check(FakeSandbox(scripted(diff=ok(DIFF_PRINT))), BASE)
    assert item.status == "fail"
    assert "debug output: app/api/x.py" in item.detail


def test_changed_file_names_from_the_agent_are_quoted() -> None:
    sandbox = FakeSandbox(scripted(names=ok("app/x.py; touch /tmp/pwn.py\n")))
    clean_state_check(sandbox, BASE)
    [ruff] = [c for c in sandbox.commands if c.startswith("ruff")]
    assert "'app/x.py; touch /tmp/pwn.py'" in ruff


def test_repository_without_migrations_skips_the_head_check() -> None:
    """A repository with no Alembic configuration (the boltons worked example): `alembic heads`
    never runs, so it cannot fail the gate or push the agent into adding a fake migration."""
    sandbox = FakeSandbox(scripted(heads=fail("FAILED: No 'script_location' key found")))
    item = clean_state_check(sandbox, BASE, migrations=False)
    assert item.status == "pass", item.detail
    assert "skipped: no migrations configured" in item.detail
    assert not any(c.startswith("alembic") for c in sandbox.commands)


def test_repository_with_migrations_still_needs_one_head() -> None:
    sandbox = FakeSandbox(scripted(heads=ok("")))
    item = clean_state_check(sandbox, BASE, migrations=True)
    assert item.status == "fail"
    assert "migration heads: 0 (expected 1)" in item.detail
    assert "alembic heads" in sandbox.commands


def test_without_a_base_commit_only_status_and_heads_are_checked() -> None:
    sandbox = FakeSandbox(scripted())
    item = clean_state_check(sandbox, "")
    assert item.status == "pass"
    assert not any(c.startswith("git diff") for c in sandbox.commands)


# Gate bug (2026-10-17): ruff 0.17.1 in the agent image enables more rules by default (B008, I001)
# than TeamTrack's code meets, and TeamTrack has no ruff config, so a change to any router file
# (FastAPI's Depends(...) defaults) failed the clean-state item, even the course's reference code.
# Without a repository config the gate now pins ruff's documented default rule set.


def test_ruff_runs_the_pinned_default_rules_when_the_repository_has_no_config() -> None:
    sandbox = FakeSandbox(scripted(names=ok("app/api/issues.py\n")))
    clean_state_check(sandbox, BASE)
    [ruff] = [c for c in sandbox.commands if c.startswith("ruff")]
    assert "--select E4,E7,E9,F" in ruff


def test_a_repository_ruff_config_is_used_as_it_is() -> None:
    sandbox = FakeSandbox(scripted(names=ok("app/api/issues.py\n")))
    clean_state_check(sandbox, BASE, ruff_select=None)
    [ruff] = [c for c in sandbox.commands if c.startswith("ruff")]
    assert "--select" not in ruff
