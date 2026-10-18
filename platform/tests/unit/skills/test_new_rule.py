"""house-rules/scripts/new_rule.py: scaffold a rule doc, a check stub, and a failing test stub."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from shipharness.layout import find_repo_root
from tests.unit.skills.helpers import load_script

REPO = find_repo_root(Path(__file__))
SCRIPT = REPO / "use-in-your-repo" / "skills" / "house-rules" / "scripts" / "new_rule.py"
TITLE = "Soft-deleted rows never appear"


@pytest.fixture(scope="module")
def new_rule() -> ModuleType:
    return load_script(SCRIPT, "house_rules_new_rule")


def scaffold(new_rule: ModuleType, root: Path, *extra: str) -> int:
    return new_rule.main(["--id", "Example", "--title", TITLE, "--root", str(root), *extra])


def test_creates_rule_doc_check_and_test(new_rule: ModuleType, tmp_path: Path) -> None:
    assert scaffold(new_rule, tmp_path) == 0
    doc = tmp_path / "docs" / "rules" / "Example-soft-deleted-rows-never-appear.md"
    check = tmp_path / "checks" / "check_example_soft_deleted_rows_never_appear.py"
    test = tmp_path / "tests" / "test_check_example_soft_deleted_rows_never_appear.py"
    for path in (doc, check, test):
        assert path.is_file(), path
    text = doc.read_text(encoding="utf-8")
    assert text.startswith(f"# Example {TITLE}")
    assert "{{" not in text and "}}" not in text
    assert "checks/check_example_soft_deleted_rows_never_appear.py" in text
    for heading in ("## Rule", "## Why", "## How it is checked", "## Error message"):
        assert heading in text
    compile(check.read_text(encoding="utf-8"), str(check), "exec")
    compile(test.read_text(encoding="utf-8"), str(test), "exec")


def test_check_stub_runs_and_prints_grep_friendly_summary(
    new_rule: ModuleType, tmp_path: Path
) -> None:
    scaffold(new_rule, tmp_path)
    check = tmp_path / "checks" / "check_example_soft_deleted_rows_never_appear.py"
    result = subprocess.run(
        [sys.executable, str(check), str(tmp_path)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Example: 0 new violations"


def test_test_stub_fails_until_the_seeded_violation_is_written(
    new_rule: ModuleType, tmp_path: Path
) -> None:
    scaffold(new_rule, tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "1 failed, 1 passed" in result.stdout, result.stdout


def test_refuses_to_overwrite_without_force(new_rule: ModuleType, tmp_path: Path) -> None:
    assert scaffold(new_rule, tmp_path) == 0
    assert scaffold(new_rule, tmp_path) == 1
    assert scaffold(new_rule, tmp_path, "--force") == 0


def test_custom_slug_and_dirs(new_rule: ModuleType, tmp_path: Path) -> None:
    code = scaffold(
        new_rule, tmp_path, "--slug", "soft-delete", "--docs-dir", "rules", "--checks-dir", "lint"
    )
    assert code == 0
    assert (tmp_path / "rules" / "Example-soft-delete.md").is_file()
    assert (tmp_path / "lint" / "check_example_soft_delete.py").is_file()


@pytest.mark.parametrize("rule_id", ["", "8R", "R 8", "Example/../x"])
def test_rejects_bad_rule_ids(new_rule: ModuleType, tmp_path: Path, rule_id: str) -> None:
    with pytest.raises(SystemExit):
        new_rule.main(["--id", rule_id, "--title", TITLE, "--root", str(tmp_path)])


def test_dry_run_writes_nothing(new_rule: ModuleType, tmp_path: Path) -> None:
    assert scaffold(new_rule, tmp_path, "--dry-run") == 0
    assert list(tmp_path.iterdir()) == []
