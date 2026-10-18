"""Review minors M1 (truncation trailer, tool logs outside the workspace) and M6 (host-side limits
in search and read_file)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shipharness.runner.models import ToolCall
from shipharness.runner.tools import MAX_FILE_BYTES, MAX_LINE_CHARS, ToolBox
from shipharness.sandbox import ExecResult, FakeSandbox


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    return root


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall(call_id=f"c-{name}", name=name, arguments=arguments)  # type: ignore[arg-type]


def box(ws: Path, **kwargs: object) -> ToolBox:
    sandbox = kwargs.pop("sandbox", None) or FakeSandbox()
    return ToolBox(ws, sandbox, None, "r-1", "harness", **kwargs)  # type: ignore[arg-type]


# --- M1 -------------------------------------------------------------------------------------


def test_trailer_tells_the_agent_to_narrow_the_command(ws: Path) -> None:
    sandbox = FakeSandbox({"cat": ExecResult(exit_code=0, output="x" * 20_000, duration_ms=1)})
    result = box(ws, sandbox=sandbox, tool_log_dir=ws.parent / "logs").execute(
        call("run", command="cat big.log", timeout_s=None)
    )
    trailer = result.output.splitlines()[-1]
    assert trailer.startswith("[truncated: 12007 more chars;")  # 20,000 + "exit=0\n" - 8,000
    assert "grep" in trailer and "tail" in trailer
    assert "outside the workspace" in trailer
    assert "logs" not in trailer and "c-run" not in trailer  # no path the agent cannot read
    assert result.full_output_path is not None
    assert ws.resolve() not in Path(result.full_output_path).resolve().parents


def test_default_tool_log_dir_is_outside_the_workspace(ws: Path) -> None:
    assert ws.resolve() not in box(ws).tool_log_dir.resolve().parents


def test_tool_log_dir_inside_the_workspace_is_refused(ws: Path) -> None:
    with pytest.raises(ValueError, match="outside the workspace"):
        box(ws, tool_log_dir=ws / ".shipharness" / "tool-logs")


# --- M6: read_file ---------------------------------------------------------------------------


def test_read_file_refuses_files_over_the_size_cap(ws: Path) -> None:
    (ws / "big.txt").write_bytes(b"a\n" * (MAX_FILE_BYTES // 2 + 1))
    result = box(ws).execute(call("read_file", path="big.txt", start_line=None, max_lines=None))
    assert result.ok is False
    assert "too large" in result.output
    assert "grep" in result.output


def test_read_file_caps_each_line(ws: Path) -> None:
    (ws / "wide.txt").write_text("b" * (MAX_LINE_CHARS + 500) + "\nshort\n", encoding="utf-8")
    result = box(ws).execute(call("read_file", path="wide.txt", start_line=None, max_lines=None))
    first = result.output.splitlines()[1]
    assert len(first) < MAX_LINE_CHARS + 100
    assert first.endswith("[line cut: 500 more chars]")
    assert "short" in result.output


# --- M6: search ------------------------------------------------------------------------------


def test_search_skips_files_over_the_size_cap_and_says_so(ws: Path) -> None:
    (ws / "huge.txt").write_bytes(b"needle\n" + b"x" * MAX_FILE_BYTES)
    (ws / "small.txt").write_text("needle\n", encoding="utf-8")
    result = box(ws).execute(call("search", pattern="needle", path=None, max_results=None))
    assert "small.txt:1: needle" in result.output
    assert "huge.txt:" not in result.output
    assert "skipped 1 file over" in result.output


def test_search_only_scans_the_first_chars_of_a_line(ws: Path) -> None:
    (ws / "wide.txt").write_text("a" * (MAX_LINE_CHARS + 10) + "needle\n", encoding="utf-8")
    result = box(ws).execute(call("search", pattern="needle", path=None, max_results=None))
    assert "wide.txt" not in result.output


def test_search_stops_at_the_time_budget(ws: Path) -> None:
    result = box(ws, search_time_budget_s=0.0).execute(
        call("search", pattern="def", path=None, max_results=None)
    )
    assert result.ok
    assert "app/main.py" not in result.output
    assert "time budget" in result.output and "narrow" in result.output
