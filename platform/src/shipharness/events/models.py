"""Event envelope and per-type data models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Arm = Literal["bare", "harness"]

EventType = Literal[
    "run_start",
    "sandbox_start",
    "sandbox_usage",
    "sandbox_denied",
    "turn",
    "tool_call",
    "tool_result",
    "harness_decision",
    "blocked",
    "session_stop",
    "session_resume",
    "test_proposed",
    "test_filter_result",
    "check_progress",
    "check_result",
    "mutant_result",
    "reviewer_output",
    "gate_result",
    "claim",
    "primary_verdict",
    "verdict",
    "cost",
    "screenshot",
    "trace_link",
    "run_end",
]


class _Data(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunStart(_Data):
    spec: dict[str, Any]
    policy_summary: str


class SandboxStart(_Data):
    container_id: str
    image: str
    network: str
    cpus: float
    memory_mb: int
    pids_limit: int
    user: str
    read_only_root: bool
    unsandboxed: bool


class SandboxUsage(_Data):
    cpu_pct: float
    mem_mb: float
    mem_limit_mb: float
    pids: int
    time_left_s: float


class SandboxDenied(_Data):
    command: str
    reason_code: Literal[
        "network",
        "write_outside_workspace",
        "memory",
        "pids",
        "timeout",
        "path_outside_workspace",
    ]
    detail: str


class Turn(_Data):
    session_index: int
    turn: int
    turns_left: int
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    message_excerpt: str


class ToolCallData(_Data):
    call_id: str
    name: str
    target: str


class ToolResultData(_Data):
    call_id: str
    ok: bool
    exit_code: int | None
    duration_ms: int
    files_changed: list[str]
    output_excerpt: str


class HarnessDecisionData(_Data):
    kind: str
    layer: str
    message: str
    paths: list[str] = []
    data: dict[str, Any] = {}


class Blocked(_Data):
    phase: Literal["build", "test"]
    paths: list[str]
    action: Literal["reject_patch", "revert"]
    reason: str


class SessionStop(_Data):
    session_index: int
    ended_by: str
    end_sha: str
    handoff_path: str | None


class SessionResume(_Data):
    session_index: int
    start_sha: str
    prefix_blocks: list[str]


class TestProposed(_Data):
    test_id: str
    phase: Literal["build", "test"]


class TestFilterResult(_Data):
    test_id: str
    filter: int
    passed: bool
    reason: str


class CheckProgress(_Data):
    check: str
    done: int
    total: int
    label: str


class CheckResultData(_Data):
    check: str
    passed: bool
    new_violations: int
    baseline_violations: int
    total_probes: int
    findings: list[dict[str, Any]]
    duration_ms: int
    seed: int | None = None


class MutantResult(_Data):
    mutant_id: str
    set: Literal["filter", "referee"]
    outcome: Literal["killed", "survived", "timeout", "error"]
    killed_by: str | None


class ReviewerOutput(_Data):
    findings: list[dict[str, Any]]
    tenant_isolation_risk: Literal["none", "possible", "likely"]
    verdict: Literal["accept", "reject"]
    summary: str


class GateResultData(_Data):
    gate_id: str
    items: list[dict[str, Any]]
    passed: bool
    feedback: str


class Claim(_Data):
    phase: Literal["build", "test"]
    claim: Literal["done", "not_done", "none"]
    summary: str
    gate_id: str | None


class PrimaryVerdict(_Data):
    """Sent by the referee as soon as the checks the primary measure reads have finished, before
    the secondary checks. `passed` and `values` equal the final record's `passed_primary` and
    `primary` unless the referee then fails to finish judging (the `verdict` event says so)."""

    arm: Arm
    run_id: str
    feature_id: str
    primary_measure: str
    passed: bool
    values: dict[str, float | int | bool]
    elapsed_s: float  # since the arm ended (since judging began, for a replay or swap test)


class Verdict(_Data):
    primary: dict[str, float | int | bool]
    passed_primary: bool
    summary: str


class Cost(_Data):
    scope: str
    model: str
    call_usd: float
    run_usd: float
    session_usd: float
    limit_usd: float


class Screenshot(_Data):
    path: str
    view: Literal["board", "issue", "conflict"]
    as_user: str
    overlays: list[dict[str, Any]]


class TraceLink(_Data):
    url: str
    kind: Literal["agent", "referee", "experiment", "comparison"]


class RunEnd(_Data):
    status: str
    claim: str
    cost_usd: float
    turns_total: int
    wall_s: float


EVENT_DATA_MODELS: dict[str, type[_Data]] = {
    "run_start": RunStart,
    "sandbox_start": SandboxStart,
    "sandbox_usage": SandboxUsage,
    "sandbox_denied": SandboxDenied,
    "turn": Turn,
    "tool_call": ToolCallData,
    "tool_result": ToolResultData,
    "harness_decision": HarnessDecisionData,
    "blocked": Blocked,
    "session_stop": SessionStop,
    "session_resume": SessionResume,
    "test_proposed": TestProposed,
    "test_filter_result": TestFilterResult,
    "check_progress": CheckProgress,
    "check_result": CheckResultData,
    "mutant_result": MutantResult,
    "reviewer_output": ReviewerOutput,
    "gate_result": GateResultData,
    "claim": Claim,
    "primary_verdict": PrimaryVerdict,
    "verdict": Verdict,
    "cost": Cost,
    "screenshot": Screenshot,
    "trace_link": TraceLink,
    "run_end": RunEnd,
}


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1] = 1
    ab_id: str | None
    run_id: str | None
    arm: Arm | None
    seq: int
    ts: str
    type: EventType
    data: dict[str, Any]
    recorded: bool = False
