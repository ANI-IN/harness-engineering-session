from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shipharness.config import Settings
from shipharness.events import EventBus, read_events
from shipharness.harness.decisions import HarnessDecision
from shipharness.runner.models import ToolCall
from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace
from shipharness.runner.tools import TOOL_NAMES, TOOL_SCHEMAS, ToolBox, truncate
from shipharness.sandbox import ExecResult, FakeSandbox, LocalSandbox, default_policy


def git(ws: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (ws / "README.md").write_text("hello\n", encoding="utf-8")
    git(ws, "init", "-q")
    git(ws, "-c", "user.name=t", "-c", "user.email=t@x", "add", ".")
    git(ws, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "init")
    return ws


def box(ws: Path, sandbox=None, bus=None, guard=None) -> ToolBox:  # type: ignore[no-untyped-def]
    return ToolBox(
        ws,
        sandbox or FakeSandbox(),
        bus,
        "r-1",
        "bare",
        guard=guard,
        tool_log_dir=ws.parent / "tool-logs",
    )


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall(call_id=f"c-{name}", name=name, arguments=arguments)  # type: ignore[arg-type]


# --- schemas ---------------------------------------------------------------------------------


def test_seven_tools_in_fixed_order() -> None:
    assert TOOL_NAMES == (
        "list_dir",
        "read_file",
        "search",
        "apply_patch",
        "run",
        "run_visible_tests",
        "finish",
    )
    assert [t["name"] for t in TOOL_SCHEMAS] == list(TOOL_NAMES)


def test_every_schema_is_strict_with_all_properties_required() -> None:
    for tool in TOOL_SCHEMAS:
        params = tool["parameters"]
        assert tool["type"] == "function"
        assert tool["strict"] is True
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


def test_schema_json_is_byte_stable() -> None:
    from importlib import reload

    import shipharness.runner.tools as tools

    first = json.dumps(tools.TOOL_SCHEMAS)
    reload(tools)
    assert json.dumps(tools.TOOL_SCHEMAS) == first


def test_finish_claim_enum() -> None:
    finish = TOOL_SCHEMAS[-1]["parameters"]["properties"]
    assert finish["claim"]["enum"] == ["done", "not_done"]


# --- paths -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["../x", "/etc/passwd", "C:\\Windows\\x", "app/../../x", "\\\\srv\\s"]
)
def test_paths_outside_workspace_are_refused(repo: Path, bad: str) -> None:
    with pytest.raises(PathOutsideWorkspace):
        resolve_in_workspace(repo, bad)


def test_symlink_escaping_workspace_is_refused(repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("x", encoding="utf-8")
    try:
        os.symlink(target, repo / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    with pytest.raises(PathOutsideWorkspace):
        resolve_in_workspace(repo, "link.txt")


def test_read_outside_workspace_reports_denial(repo: Path, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        result = box(repo, bus=bus).execute(
            call("read_file", path="../x", start_line=None, max_lines=None)
        )
    assert result.ok is False
    assert "path_outside_workspace" in result.output
    [denied] = [e for e in read_events(log) if e.type == "sandbox_denied"]
    assert denied.data["reason_code"] == "path_outside_workspace"


# --- read / list / search ----------------------------------------------------------------------


def test_read_file_numbers_lines(repo: Path) -> None:
    result = box(repo).execute(
        call("read_file", path="app/main.py", start_line=None, max_lines=None)
    )
    assert result.ok
    assert result.output.splitlines()[0] == "[lines 1-2 of 2] app/main.py"
    assert "1  def add(a, b):" in result.output


def test_read_binary_file_is_decoded_with_replacement(repo: Path) -> None:
    (repo / "blob.bin").write_bytes(b"\xff\xfe\x00abc")
    result = box(repo).execute(call("read_file", path="blob.bin", start_line=None, max_lines=None))
    assert result.ok
    assert "abc" in result.output


def test_list_dir_marks_directories_and_skips_git(repo: Path) -> None:
    result = box(repo).execute(call("list_dir", path=".", depth=None))
    lines = result.output.splitlines()
    assert "app/" in lines
    assert "README.md" in lines
    assert not any(line.startswith(".git") for line in lines)


def test_search_finds_matches(repo: Path) -> None:
    result = box(repo).execute(call("search", pattern=r"def \w+", path=None, max_results=None))
    assert "app/main.py:1: def add(a, b):" in result.output


def test_search_invalid_regex_is_an_error_result(repo: Path) -> None:
    result = box(repo).execute(call("search", pattern="(", path=None, max_results=None))
    assert result.ok is False
    assert "invalid pattern" in result.output


# --- argument and name errors ------------------------------------------------------------------


def test_malformed_arguments_produce_error_result(repo: Path) -> None:
    result = box(repo).execute(call("read_file", path=3))
    assert result.ok is False
    assert "invalid arguments" in result.output


def test_unknown_tool_produces_error_result(repo: Path) -> None:
    result = box(repo).execute(ToolCall.model_construct(call_id="c", name="rm_rf", arguments={}))
    assert result.ok is False
    assert "unknown tool" in result.output


# --- run, truncation, visible tests ----------------------------------------------------------


def test_large_output_is_truncated_and_saved(repo: Path) -> None:
    big = "x" * 5_000_000
    sandbox = FakeSandbox({"cat": ExecResult(exit_code=0, output=big, duration_ms=1)})
    result = box(repo, sandbox=sandbox).execute(call("run", command="cat big.log", timeout_s=None))
    assert len(result.output) <= 8_200
    assert "[truncated:" in result.output
    assert result.full_output_path is not None
    saved = Path(result.full_output_path).read_text(encoding="utf-8")
    assert saved.endswith(big)


def test_truncate_helper() -> None:
    text, cut = truncate("abc", limit=10)
    assert (text, cut) == ("abc", False)
    text, cut = truncate("a" * 20, limit=10)
    assert cut and text.startswith("a" * 10)


def test_run_reports_exit_code(repo: Path) -> None:
    sandbox = FakeSandbox({"pytest": ExecResult(exit_code=1, output="boom", duration_ms=3)})
    result = box(repo, sandbox=sandbox).execute(call("run", command="pytest -q", timeout_s=None))
    assert result.output.startswith("exit=1")
    assert result.exit_code == 1


PYTEST_OUT = """\
..F.F
=========================== short test summary info ============================
FAILED tests/visible/test_a.py::test_one - AssertionError: assert 1 == 2
FAILED tests/visible/test_b.py::test_two - KeyError: 'id'
2 failed, 3 passed in 0.42s
"""


def test_run_visible_tests_summarises_grep_friendly(repo: Path) -> None:
    sandbox = FakeSandbox(lambda _cmd: ExecResult(exit_code=1, output=PYTEST_OUT, duration_ms=9))
    result = box(repo, sandbox=sandbox).execute(call("run_visible_tests", selector=None))
    lines = result.output.splitlines()
    assert lines[0] == "passed=3 failed=2 errors=0"
    assert "FAILED tests/visible/test_a.py::test_one: AssertionError: assert 1 == 2" in lines
    assert "FAILED tests/visible/test_b.py::test_two: KeyError: 'id'" in lines


def test_run_visible_tests_rejects_selector_outside_visible(repo: Path) -> None:
    result = box(repo).execute(call("run_visible_tests", selector="tests/hidden/test_x.py"))
    assert result.ok is False


def test_run_visible_tests_on_teamtrack_runs_tests_visible_as_before(repo: Path) -> None:
    sandbox = FakeSandbox(lambda _cmd: ExecResult(exit_code=0, output="3 passed", duration_ms=1))
    selector = "tests/visible/test_a.py::test_one"
    result = box(repo, sandbox=sandbox).execute(call("run_visible_tests", selector=selector))
    assert result.ok
    assert sandbox.commands == [
        "python -m pytest tests/visible -q -rfE --no-header -p no:cacheprovider " + selector
    ]
    refused = box(repo).execute(call("run_visible_tests", selector="tests/test_a.py"))
    assert refused.output == "selector must be a pytest node inside tests/visible"


def test_run_visible_tests_uses_the_runs_test_directory(repo: Path) -> None:
    """A repository whose tests live in tests/ (the boltons worked example): the selector the
    agent gives for its new test file is accepted and pytest runs tests/, not tests/visible."""
    sandbox = FakeSandbox(lambda _cmd: ExecResult(exit_code=0, output="6 passed", duration_ms=1))
    toolbox = ToolBox(
        repo,
        sandbox,
        None,
        "r-1",
        "harness",
        tool_log_dir=repo.parent / "tool-logs",
        visible_tests_dir="tests",
    )
    selector = "tests/test_queueutils_generated.py"
    result = toolbox.execute(call("run_visible_tests", selector=selector))
    assert result.ok, result.output
    assert sandbox.commands == [
        "python -m pytest tests -q -rfE --no-header -p no:cacheprovider " + selector
    ]
    refused = toolbox.execute(call("run_visible_tests", selector="other/test_x.py"))
    assert refused.output == "selector must be a pytest node inside tests"


def test_tool_schemas_name_the_runs_test_directory() -> None:
    from shipharness.runner.tools import tool_schemas

    assert json.dumps(tool_schemas("tests/visible")) == json.dumps(TOOL_SCHEMAS)
    [tool] = [t for t in tool_schemas("tests") if t["name"] == "run_visible_tests"]
    text = json.dumps(tool)
    assert "tests/visible" not in text
    assert "(tests)" in tool["description"]


# --- apply_patch ----------------------------------------------------------------------------

NEW_FILE_PATCH = """\
--- /dev/null
+++ b/app/new.py
@@ -0,0 +1,2 @@
+def sub(a, b):
+    return a - b
"""

ESCAPE_PATCH = """\
--- /dev/null
+++ b/../outside.txt
@@ -0,0 +1 @@
+pwned
"""


@pytest.fixture
def local_sandbox(repo: Path) -> LocalSandbox:
    return LocalSandbox(default_policy(Settings(_env_file=None)), repo, None, "r-1", "bare")


def test_apply_patch_adds_file(repo: Path, local_sandbox: LocalSandbox) -> None:
    result = box(repo, sandbox=local_sandbox).execute(call("apply_patch", patch=NEW_FILE_PATCH))
    assert result.ok, result.output
    assert (repo / "app" / "new.py").read_text(encoding="utf-8").startswith("def sub")
    assert result.files_changed == ["app/new.py"]


def test_apply_patch_outside_workspace_is_refused_before_writing(
    repo: Path, local_sandbox: LocalSandbox
) -> None:
    result = box(repo, sandbox=local_sandbox).execute(call("apply_patch", patch=ESCAPE_PATCH))
    assert result.ok is False
    assert "path_outside_workspace" in result.output
    assert not (repo.parent / "outside.txt").exists()


def test_apply_patch_that_does_not_apply_reports_reason(
    repo: Path, local_sandbox: LocalSandbox
) -> None:
    bad = "--- a/app/main.py\n+++ b/app/main.py\n@@ -1 +1 @@\n-nothing here\n+x\n"
    result = box(repo, sandbox=local_sandbox).execute(call("apply_patch", patch=bad))
    assert result.ok is False
    assert "patch does not apply" in result.output


def test_guard_block_stops_the_tool(repo: Path, local_sandbox: LocalSandbox) -> None:
    def guard(_call: ToolCall) -> HarnessDecision:
        return HarnessDecision(
            kind="block", layer="scope", message="app/new.py is out of scope", paths=["app/new.py"]
        )

    result = box(repo, sandbox=local_sandbox, guard=guard).execute(
        call("apply_patch", patch=NEW_FILE_PATCH)
    )
    assert result.ok is False
    assert result.output.startswith("BLOCKED: app/new.py is out of scope")
    assert not (repo / "app" / "new.py").exists()


def test_run_reports_files_changed(repo: Path, local_sandbox: LocalSandbox) -> None:
    cmd = f"\"{sys.executable}\" -c \"open('made.txt', 'w').write('x')\""
    result = box(repo, sandbox=local_sandbox).execute(call("run", command=cmd, timeout_s=None))
    assert result.files_changed == ["made.txt"]


def test_run_tool_caps_the_agent_timeout_at_the_tool_limit(tmp_path: Path) -> None:
    seen: list[int] = []

    class Recording(FakeSandbox):
        def exec(self, command: str, timeout_s: int) -> ExecResult:
            seen.append(timeout_s)
            return super().exec(command, timeout_s)

    repo = tmp_path / "ws"
    repo.mkdir()
    toolbox = box(repo, sandbox=Recording())
    toolbox.execute(call("run", command="pytest -q", timeout_s=99999))
    assert seen == [toolbox.tool_timeout_s]
