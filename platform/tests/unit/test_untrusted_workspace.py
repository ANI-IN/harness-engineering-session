"""The arm workspace is untrusted: nothing in it (git config, links, file bytes, model-chosen ids)
may make host-side code run commands, read outside the workspace, write outside the run dir, or
crash the run. Findings C1, C2, I1, I5, M2 of the M3 final review."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from shipharness.events import EventBus, read_events
from shipharness.runner import git as run_git
from shipharness.runner.models import ToolCall
from shipharness.runner.tools import ToolBox
from shipharness.sandbox import ExecResult, FakeSandbox

from .fakes import fake_openai_key

GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@x"]


def git(ws: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "main.py").write_text("x = 1\n", encoding="utf-8")
    git(ws, "init", "-q")
    git(ws, *GIT_ID, "add", ".")
    git(ws, *GIT_ID, "commit", "-qm", "init")
    return ws


def toolbox(ws: Path, sandbox=None, bus=None) -> ToolBox:  # type: ignore[no-untyped-def]
    return ToolBox(
        ws, sandbox or FakeSandbox(), bus, "r-1", "bare", tool_log_dir=ws.parent / "tool-logs"
    )


def call(name: str, call_id: str = "c1", **arguments: object) -> ToolCall:
    return ToolCall(call_id=call_id, name=name, arguments=arguments)  # type: ignore[arg-type]


def plant_hostile_git_config(ws: Path, marker: Path) -> None:
    """Agent-controlled repo config that would execute a command if host git honoured it."""
    command = f"touch {marker.as_posix()}"
    git(ws, "config", "core.fsmonitor", command)
    git(ws, "config", "filter.evil.clean", command)
    git(ws, "config", "diff.external", command)
    (ws / ".gitattributes").write_text("* filter=evil diff=evil\n", encoding="utf-8")
    git(ws, "config", "diff.evil.textconv", command)
    (ws / "app" / "main.py").write_text("x = 2\n", encoding="utf-8")


# --- C1: host-side git never executes agent-configured commands --------------------------------


def test_files_changed_snapshot_does_not_run_agent_git_config(repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "pwned-snapshot"
    plant_hostile_git_config(repo, marker)
    sandbox = FakeSandbox({"echo": ExecResult(exit_code=0, output="", duration_ms=1)})
    result = toolbox(repo, sandbox).execute(call("run", command="echo hi", timeout_s=None))
    assert result.ok
    assert not marker.exists(), "host git executed an agent-configured command"


def test_write_diff_does_not_run_agent_git_config(repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "pwned-diff"
    base = run_git.initial_sha(repo)
    plant_hostile_git_config(repo, marker)
    out = run_git.write_diff(repo, base, tmp_path / "diff.patch")
    assert not marker.exists(), "host git executed an agent-configured command"
    assert out is not None
    assert b"x = 2" in out.read_bytes()


def test_write_diff_keeps_non_utf8_bytes_exactly(repo: Path, tmp_path: Path) -> None:
    base = run_git.initial_sha(repo)
    (repo / "app" / "latin1.txt").write_bytes(b"caf\xe9\n")
    out = run_git.write_diff(repo, base, tmp_path / "diff.patch")
    assert out is not None
    assert b"caf\xe9" in out.read_bytes()


def test_files_changed_still_reports_changes_without_git(repo: Path) -> None:
    def script(command: str) -> ExecResult:
        (repo / "app" / "new.py").write_text("y = 1\n", encoding="utf-8")
        (repo / "app" / "main.py").write_text("x = 3\n", encoding="utf-8")
        return ExecResult(exit_code=0, output="", duration_ms=1)

    result = toolbox(repo, FakeSandbox(script)).execute(call("run", command="edit", timeout_s=None))
    assert result.files_changed == ["app/main.py", "app/new.py"]


# --- C2: links that leave the workspace are never followed ----------------------------------------


def make_dir_link(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("cannot create directory links")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=False
        )
        if result.returncode != 0:
            pytest.skip("cannot create a junction")


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    folder = tmp_path / "outside"
    folder.mkdir()
    (folder / "secret.env").write_text("SECRET_MARKER=1\n", encoding="utf-8")
    return folder


def test_search_does_not_follow_links_out_of_the_workspace(repo: Path, outside: Path) -> None:
    make_dir_link(repo / "lnk", outside)
    result = toolbox(repo).execute(
        call("search", pattern="SECRET_MARKER", path=None, max_results=None)
    )
    assert "SECRET_MARKER" not in result.output


def test_list_dir_does_not_crash_or_descend_into_outside_links(repo: Path, outside: Path) -> None:
    make_dir_link(repo / "lnk", outside)
    result = toolbox(repo).execute(call("list_dir", path=".", depth=3))
    assert result.ok
    assert "secret.env" not in result.output


def test_apply_patch_refuses_when_git_dir_is_a_link(tmp_path: Path, outside: Path) -> None:
    ws = tmp_path / "ws2"
    ws.mkdir()
    real = tmp_path / "realrepo"
    real.mkdir()
    git(real, "init", "-q")
    make_dir_link(ws / ".git", real / ".git")
    patch = "--- /dev/null\n+++ b/a.py\n@@ -0,0 +1 @@\n+x = 1\n"
    result = toolbox(ws).execute(call("apply_patch", patch=patch))
    assert result.ok is False
    assert not (real / ".git" / "shipharness-patch.diff").exists()


# --- I1: tool failures become error results ---------------------------------------------


def test_unexpected_tool_exception_becomes_an_error_result(repo: Path) -> None:
    def boom(command: str) -> ExecResult:
        raise RuntimeError("sandbox exploded")

    result = toolbox(repo, FakeSandbox(boom)).execute(call("run", command="x", timeout_s=None))
    assert result.ok is False
    assert "RuntimeError" in result.output


# --- I5: key-shaped strings never leave a tool result or the run log ---------------------------


def test_tool_output_and_logs_mask_keys(repo: Path, tmp_path: Path) -> None:
    key = fake_openai_key()
    big = f"OPENAI_API_KEY={key}\n" + "x" * 20_000
    sandbox = FakeSandbox({"cat": ExecResult(exit_code=0, output=big, duration_ms=1)})
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        result = toolbox(repo, sandbox, bus).execute(
            call("run", command="cat .env", timeout_s=None)
        )
        bus.publish(
            "tool_result",
            {
                "call_id": "c1",
                "ok": True,
                "exit_code": 0,
                "duration_ms": 1,
                "files_changed": [],
                "output_excerpt": big[:500],
            },
            run_id="r-1",
            arm="bare",
        )
    assert key not in result.output
    assert result.full_output_path is not None
    assert key not in Path(result.full_output_path).read_text(encoding="utf-8")
    assert key not in log.read_text(encoding="utf-8")
    assert [e.type for e in read_events(log)] == ["tool_result"]


# --- M2: model-chosen call ids cannot steer host file writes --------------------------------------


def test_call_id_cannot_escape_the_tool_log_dir(repo: Path) -> None:
    sandbox = FakeSandbox({"cat": ExecResult(exit_code=0, output="y" * 20_000, duration_ms=1)})
    box = toolbox(repo, sandbox)
    result = box.execute(call("run", call_id="../../escaped", command="cat x", timeout_s=None))
    assert result.full_output_path is not None
    written = Path(result.full_output_path).resolve()
    assert box.tool_log_dir.resolve() in written.parents
    assert not (repo.parent.parent / "escaped.txt").exists()


def test_snapshot_tree_captures_uncommitted_work_without_agent_git_config(
    repo: Path, tmp_path: Path
) -> None:
    """Session snapshots (S2 measure) see the working tree whether or not the arm commits, and
    never run commands from the agent's .git/config."""
    marker = tmp_path / "pwned"
    plant_hostile_git_config(repo, marker)
    store = tmp_path / "snapshots" / "store.git"
    first = run_git.snapshot_tree(repo, store)
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "new.py").write_text("y = 1\n", encoding="utf-8")  # untracked, never committed
    second = run_git.snapshot_tree(repo, store)
    assert first and second and first != second
    out = run_git.write_tree_diff(store, first, second, tmp_path / "s.patch")
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "+x = 2" in text and "+y = 1" in text
    assert not marker.exists()
    assert run_git.snapshot_tree(repo, store) == second  # same content, same tree
