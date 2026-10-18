"""Runner data models."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from shipharness.events import Arm
from shipharness.harness.decisions import LayerName

Phase = Literal["build", "test"]
ToolName = Literal[
    "list_dir", "read_file", "search", "apply_patch", "run", "run_visible_tests", "finish"
]
ClaimValue = Literal["done", "not_done", "none"]
RunStatus = Literal["completed", "ABORTED: cap", "ABORTED: timeout", "ERROR"]
TEAMTRACK_VISIBLE_TESTS = "tests/visible"
_PART = r"[A-Za-z0-9_.][A-Za-z0-9_.-]*"  # never starts with "-" (pytest would read an option)
_RELATIVE_DIR = re.compile(rf"^{_PART}(/{_PART})*$")


def checked_tests_dir(value: str) -> str:
    """A repository-relative directory in POSIX form, safe to put in a shell command: no
    absolute path, no `.` or `..` part (except "." alone), and only letters, digits, `_`, `.`,
    `-` (not first), and `/`. A trailing `/` is dropped."""
    text = value.rstrip("/") if value not in ("", "/") else value
    parts = text.split("/")
    if not _RELATIVE_DIR.match(text) or ".." in parts or (text != "." and "." in parts):
        raise ValueError(f"not a repository-relative directory: {value!r}")
    return text


class AgentRunSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    ab_id: str | None = None
    arm: Arm
    feature_id: str
    checkpoint: str
    ticket_text: str
    variant: str = "canonical"
    layers: frozenset[LayerName] = frozenset()
    phases: tuple[Phase, ...] = ("build", "test")
    session_budget: list[int] = [30]
    test_phase_turns: int = 12
    allowed_paths: dict[Phase, list[str]] = {}
    model: str
    reasoning_effort: str
    max_output_tokens: int = 8000
    service_tier: str = "auto"
    run_timeout_s: int = 300  # agent time limit (RUN_TIMEOUT_S; class profile: 420)
    profile: str = "standard"  # run profile (config/profiles.py), the same for both arms
    single_arm: bool = False  # True: harness arm alone (`ab --arms harness`), not an A/B
    constructed: bool = False  # True: a constructed example (scripted steps, no model)
    cost_limit_usd: float = 0.20
    workspace: Path
    # Where the visible tests live: run_visible_tests, the verify gate, and the test-phase filters
    # use it. TeamTrack keeps tests/visible; testgen sets the directory of the repo's tests.
    visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS

    @field_validator("visible_tests_dir")
    @classmethod
    def _check_visible_tests_dir(cls, value: str) -> str:
        return checked_tests_dir(value)

    def public_dict(self) -> dict[str, Any]:
        """Spec for events and traces (no host paths). The visible-test directory is listed only
        when it is not TeamTrack's tests/visible, so TeamTrack events keep their shape."""
        data = self.model_dump(mode="json", exclude={"workspace"})
        data["layers"] = sorted(self.layers)
        if self.visible_tests_dir == TEAMTRACK_VISIBLE_TESTS:
            del data["visible_tests_dir"]
        return data


class SessionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    phase: Phase
    turns: int
    ended_by: Literal[
        "claim_done", "claim_not_done", "turn_budget", "cap", "timeout", "error", "no_tool_call"
    ]
    start_sha: str
    end_sha: str
    # Working-tree snapshots (runner/git.py snapshot_tree), committed or not; "" when not taken.
    start_tree: str = ""
    end_tree: str = ""


class AgentRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    arm: Arm
    status: RunStatus
    claim: ClaimValue  # from the last finish() call; "none" if never called
    claim_summary: str
    claims: dict[Phase, ClaimValue] = {}  # last claim per phase that started; "none" if no finish
    sessions: list[SessionResult]
    phase_shas: dict[Phase, tuple[str, str]]
    diff_path: Path | None
    cost_usd: float
    turns_total: int
    wall_s: float  # total wall time: agent_wall_s + harness_wall_s
    trace_url: str | None
    error: str | None = None
    agent_wall_s: float = 0.0  # agent working time (model calls, tools); RUN_TIMEOUT_S applies
    harness_wall_s: float = 0.0  # deterministic harness work; HARNESS_TIMEOUT_S applies
    abort_reason: str | None = None  # ABORTED runs: the limit that ended the run


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    name: ToolName
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    ok: bool
    output: str  # already truncated
    full_output_path: str | None = None
    exit_code: int | None = None
    duration_ms: int = 0
    files_changed: list[str] = []
