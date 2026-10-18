"""apply_patch accepts the patch shapes models write (M6 pilot: about 80% of patches failed).

gpt-6-luna writes the context-anchored format (`*** Begin Patch`, `*** Update File:`, `@@` hunks
found by their context lines), unified hunks without line numbers, and unified hunks with wrong
counts. Each case below is the shape seen in the pilot traces, reduced to a small file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shipharness.config import Settings
from shipharness.harness.scope.guard import patch_targets
from shipharness.runner.models import ToolCall
from shipharness.runner.tools import ToolBox, patch_paths
from shipharness.sandbox import LocalSandbox, default_policy

MAIN = (
    "from x import y\n\n\ndef add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
)


def git(ws: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "main.py").write_text(MAIN, encoding="utf-8")
    (ws / "app" / "old.py").write_text("gone = True\n", encoding="utf-8")
    git(ws, "init", "-q")
    git(ws, "-c", "user.name=t", "-c", "user.email=t@x", "add", ".")
    git(ws, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "init")
    return ws


def apply(ws: Path, patch: str):  # type: ignore[no-untyped-def]
    sandbox = LocalSandbox(default_policy(Settings(_env_file=None)), ws, None, "r-1", "bare")
    box = ToolBox(ws, sandbox, None, "r-1", "bare", tool_log_dir=ws.parent / "tool-logs")
    return box.execute(ToolCall(call_id="c-1", name="apply_patch", arguments={"patch": patch}))


def main_text(ws: Path) -> str:
    return (ws / "app" / "main.py").read_text(encoding="utf-8")


def test_anchored_update_is_applied_by_context(repo: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: app/main.py\n"
        "@@ def sub(a, b):\n"
        "-    return a - b\n"
        "+    return b - a\n"
        "*** End Patch\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    assert main_text(repo).endswith("def sub(a, b):\n    return b - a\n")
    assert result.files_changed == ["app/main.py"]


def test_anchored_add_and_delete_files(repo: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Add File: app/new.py\n"
        "+def mul(a, b):\n"
        "+    return a * b\n"
        "*** Delete File: app/old.py\n"
        "*** End Patch\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    assert (repo / "app" / "new.py").read_text(encoding="utf-8") == (
        "def mul(a, b):\n    return a * b\n"
    )
    assert not (repo / "app" / "old.py").exists()
    assert result.files_changed == ["app/new.py", "app/old.py"]


def test_anchored_hunks_with_bare_at_markers_and_blank_context(repo: Path) -> None:
    # The pilot's shape: `@@` with no text, context lines, and a blank context line written
    # without its leading space.
    patch = (
        "*** Begin Patch\n"
        "*** Update File: app/main.py\n"
        "@@\n"
        "-from x import y\n"
        "+from x import y, z\n"
        "@@\n"
        " def add(a, b):\n"
        "     return a + b\n"
        "+\n"
        "+\n"
        "+def neg(a):\n"
        "+    return -a\n"
        "\n"
        "\n"
        " def sub(a, b):\n"
        "*** End Patch\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    text = main_text(repo)
    assert text.startswith("from x import y, z\n")
    assert "def neg(a):\n    return -a\n\n\ndef sub(a, b):" in text


def test_unified_diff_without_line_numbers(repo: Path) -> None:
    patch = (
        "--- app/main.py\n"
        "+++ app/main.py\n"
        "@@\n"
        " def add(a, b):\n"
        "-    return a + b\n"
        "+    return b + a\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    assert "    return b + a\n" in main_text(repo)


def test_unified_diff_with_wrong_counts(repo: Path) -> None:
    patch = (
        "--- a/app/main.py\n"
        "+++ b/app/main.py\n"
        "@@ -4,9 +4,12 @@\n"
        " def add(a, b):\n"
        "-    return a + b\n"
        "+    return b + a\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    assert "    return b + a\n" in main_text(repo)


def test_mixed_begin_patch_with_unified_headers(repo: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "--- app/main.py\n"
        "+++ app/main.py\n"
        "@@\n"
        "-    return a - b\n"
        "+    return b - a\n"
        "*** End Patch\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    assert "    return b - a\n" in main_text(repo)


def test_context_that_is_not_in_the_file_is_reported(repo: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: app/main.py\n"
        "@@\n"
        "-    return a * b\n"
        "+    return 0\n"
        "*** End Patch\n"
    )
    result = apply(repo, patch)
    assert result.ok is False
    assert "app/main.py" in result.output and "not found" in result.output
    assert main_text(repo) == MAIN


def test_anchored_path_outside_workspace_is_refused_before_writing(repo: Path) -> None:
    patch = "*** Begin Patch\n*** Add File: ../outside.txt\n+pwned\n*** End Patch\n"
    result = apply(repo, patch)
    assert result.ok is False
    assert "path_outside_workspace" in result.output
    assert not (repo.parent / "outside.txt").exists()


def test_anchored_update_of_a_missing_file_is_reported(repo: Path) -> None:
    patch = "*** Begin Patch\n*** Update File: app/none.py\n@@\n-a\n+b\n*** End Patch\n"
    result = apply(repo, patch)
    assert result.ok is False
    assert "app/none.py" in result.output


def test_anchored_move_renames_the_file(repo: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: app/old.py\n"
        "*** Move to: app/renamed.py\n"
        "@@\n"
        "-gone = True\n"
        "+gone = False\n"
        "*** End Patch\n"
    )
    result = apply(repo, patch)
    assert result.ok, result.output
    assert not (repo / "app" / "old.py").exists()
    assert (repo / "app" / "renamed.py").read_text(encoding="utf-8") == "gone = False\n"


def test_patch_paths_and_scope_targets_see_anchored_headers() -> None:
    patch = (
        "*** Begin Patch\n"
        "*** Update File: app/a.py\n"
        "*** Move to: app/b.py\n"
        "@@\n-x\n+y\n"
        "*** Add File: tests/visible/test_c.py\n+def test_c():\n+    pass\n"
        "*** Delete File: app/d.py\n"
        "*** End Patch\n"
    )
    paths, _prefixed = patch_paths(patch)
    assert paths == ["app/a.py", "app/b.py", "tests/visible/test_c.py", "app/d.py"]
    assert patch_targets(patch) == paths


def test_loop_target_names_anchored_paths() -> None:
    from shipharness.runner.loop import _target

    patch = "*** Begin Patch\n*** Update File: app/a.py\n@@\n-x\n+y\n*** End Patch\n"
    call = ToolCall(call_id="c-1", name="apply_patch", arguments={"patch": patch})
    assert _target(call) == "app/a.py"
