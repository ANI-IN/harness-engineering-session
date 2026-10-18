"""Fold run-log events into the view model behind the five console screens.

The console's only input is events; this module never reads a workspace. Every
string here can come from agent output, so templates must escape it (Jinja autoescape does).
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shipharness.ab.artifacts import is_harness_artifact
from shipharness.console.labels import (
    MEASURE_LABELS,
    check_label,
    check_short,
    claim_parts,
    filter_name,
    progress_label,
    spec_mismatch,
)
from shipharness.datasets.names import feature_label
from shipharness.events import Event

ARMS = ("bare", "harness")
RECENT_TURNS = 8
TAIL_SIZE = 40
_EDIT_TOOLS = {"apply_patch"}

_CATEGORIES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|/)AGENTS\.md$"), "map"),
    (re.compile(r"(^|/)\.agents/skills/"), "skill"),
    (re.compile(r"(^|/)docs/HANDBOOK\.md$"), "handbook"),
    (
        re.compile(
            r"(^|/)(progress\.md|session-handoff\.md|init\.sh|feature_list(\.schema)?\.json)$"
            r"|(^|/)docs/exec-plans/"
        ),
        "state",
    ),
    (
        re.compile(
            r"(^|/)ARCHITECTURE\.md$|(^|/)docs/(SECURITY|RELIABILITY|QUALITY_SCORE|PLANS)\.md$"
            r"|(^|/)docs/(design-docs|product-specs|references)/"
        ),
        "harness doc",
    ),
    (re.compile(r"(^|/)tests?/"), "test"),
)
HARNESS_CATEGORIES = {"map", "skill", "state", "harness doc"}
CATEGORY_ORDER = ("map", "skill", "harness doc", "state", "handbook", "code", "test")


def measure_values(values: dict[str, Any]) -> str:
    """Primary values as one readable line ("House rule 1: Tenant isolation, new violations 2"),
    booleans as yes / no."""
    if not values:
        return "no primary measure"
    parts = []
    for name, value in values.items():
        shown = ("yes" if value else "no") if isinstance(value, bool) else str(value)
        parts.append(f"{MEASURE_LABELS.get(name, name)} {shown}")
    return " · ".join(parts)


def _seconds_between(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max((b - a).total_seconds(), 0.0)


def categorise(path: str) -> str:
    for pattern, name in _CATEGORIES:
        if pattern.search(path):
            return name
    return "code"


@dataclass
class ToolLine:
    call_id: str
    name: str
    target: str
    ok: bool | None = None
    exit_code: int | None = None
    files_changed: list[str] = field(default_factory=list)
    output_excerpt: str = ""

    @property
    def harness_doc(self) -> bool:
        return self.name == "read_file" and categorise(self.target) in HARNESS_CATEGORIES


@dataclass
class TimelineRow:
    """A turn, or a session marker (`session_stop` / `session_resume`) in the turn list."""

    kind: str
    seq: int
    session_index: int
    turn: int = 0
    turns_left: int = 0
    message: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    tools: list[ToolLine] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # "blocked", "denied", "gate_fail"
    detail: str = ""


@dataclass
class Decision:
    seq: int
    kind: str
    layer: str
    message: str
    paths: list[str] = field(default_factory=list)


@dataclass
class FileRead:
    path: str
    category: str
    count: int = 0


@dataclass
class TestRow:
    test_id: str
    phase: str
    filters: dict[int, tuple[bool, str]] = field(default_factory=dict)

    @property
    def failed_filter(self) -> int | None:
        failed = [n for n, (ok, _) in sorted(self.filters.items()) if not ok]
        return failed[0] if failed else None

    @property
    def kept(self) -> bool | None:
        """True when all five filters passed, False on the first discard, None while pending."""
        if self.failed_filter is not None:
            return False
        return True if len(self.filters) >= 5 else None

    @property
    def discard_reason(self) -> str:
        """'Filter 4: Real assertions (mocks the unit under test)'; "" unless discarded."""
        n = self.failed_filter
        if n is None:
            return ""
        reason = self.filters[n][1]
        return f"{filter_name(n)} ({reason})" if reason else filter_name(n)


@dataclass
class GateRefusal:
    """One refused 'done': the gate attempt that failed, what failed, and what came next."""

    phase: str
    attempt: int
    failed: str
    outcome: str

    @property
    def text(self) -> str:
        return (
            f"Gate refused 'done' ({self.phase} phase, attempt {self.attempt}): {self.failed}"
            f" → {self.outcome}"
        )


@dataclass
class SessionSummary:
    index: int
    turns: int = 0
    phase: str = "build"  # "test": the test phase after the build, not a resumed build session
    ended_by: str = ""
    files: list[str] = field(default_factory=list)
    redone: list[str] = field(default_factory=list)


@dataclass
class WrongTurn:
    session_index: int
    turn: int
    seq: int
    reason: str


@dataclass
class TailLine:
    seq: int
    ts: str
    arm: str | None
    type: str
    summary: str
    recorded: bool


@dataclass
class ArmState:
    name: str
    run_start: dict[str, Any] | None = None
    sandbox: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    run_end: dict[str, Any] | None = None
    timeline: list[TimelineRow] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    denials: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    gates: list[dict[str, Any]] = field(default_factory=list)
    progress: dict[str, dict[str, Any]] = field(default_factory=dict)
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    claims: dict[str, dict[str, Any]] = field(default_factory=dict)
    verdict: dict[str, Any] | None = None
    primary: dict[str, Any] | None = None  # the latest primary_verdict
    reviewer: dict[str, Any] | None = None
    tests: dict[str, TestRow] = field(default_factory=dict)
    mutants: list[dict[str, Any]] = field(default_factory=list)
    screenshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    traces: dict[str, str] = field(default_factory=dict)
    files_read: dict[str, FileRead] = field(default_factory=dict)
    session_index: int = 1
    _calls: dict[str, ToolLine] = field(default_factory=dict)
    _session_ends: dict[int, str] = field(default_factory=dict)
    _resumed: set[int] = field(default_factory=set)  # sessions started by a session_resume
    _claimed_test: set[int] = field(default_factory=set)  # sessions with a claim of phase "test"
    _gate_phase: dict[str, str] = field(default_factory=dict)  # gate id -> phase it gated
    # Event seq and time stamp of the launch (run_start), the primary verdict, and the verdict.
    _seen: dict[str, tuple[int, str]] = field(default_factory=dict)

    # -- derived views --------------------------------------------------------------------------
    @property
    def gate(self) -> dict[str, Any] | None:
        return self.gates[-1] if self.gates else None

    @property
    def claim(self) -> dict[str, Any] | None:
        """The claim shown as "agent said": the build claim, else the latest one."""
        return self.claims.get("build") or (list(self.claims.values())[-1] if self.claims else None)

    @property
    def claim_parts(self) -> list[tuple[str, str]]:
        """Screen 1's "Agent said:" per phase: [("done", "done (build)"), ("not_done", "not done
        (test phase)")], or [("done", "done")] when the agent claimed in the build phase only."""
        return claim_parts({phase: str(data["claim"]) for phase, data in self.claims.items()})

    @property
    def secondary_pending(self) -> bool:
        """The primary verdict is in and the full verdict that follows it is not."""
        if "primary" not in self._seen:
            return False
        return self._seen.get("verdict", (0, ""))[0] < self._seen["primary"][0]

    @property
    def primary_view(self) -> dict[str, Any] | None:
        """{"passed", "values"} of the primary measure: from the full verdict once it follows the
        primary verdict (or when the log has none), else from the primary verdict."""
        if self.primary is not None and (self.verdict is None or self.secondary_pending):
            return {"passed": bool(self.primary["passed"]), "values": dict(self.primary["values"])}
        if self.verdict is not None:
            return {
                "passed": bool(self.verdict["passed_primary"]),
                "values": dict(self.verdict["primary"]),
            }
        return None

    @property
    def time_to_primary_s(self) -> float | None:
        """Seconds from the arm's launch to its primary verdict (None until both are known)."""
        launch, early = self._seen.get("launch"), self._seen.get("primary")
        return _seconds_between(launch[1], early[1]) if launch and early else None

    @property
    def time_to_verdict_s(self) -> float | None:
        """Seconds from the arm's launch to its full verdict (None while it is still running)."""
        launch, final = self._seen.get("launch"), self._seen.get("verdict")
        if not launch or not final or self.secondary_pending:
            return None
        return _seconds_between(launch[1], final[1])

    @property
    def claim_supported(self) -> bool | None:
        """Agent said done and the referee agrees (None until both are known)."""
        claim, view = self.claim, self.primary_view
        if claim is None or view is None:
            return None
        said_done = claim["claim"] == "done"
        return said_done == view["passed"]

    @property
    def spec_text(self) -> str:
        """The ticket the arm was given (run_start spec), for reading test discards against it."""
        spec = (self.run_start or {}).get("spec") or {}
        return str(spec.get("ticket_text") or "") if isinstance(spec, dict) else ""

    def spec_mismatch(self, test: TestRow) -> tuple[str, str] | None:
        """(returned, expected) for a Filter 2 discard whose failed assertion expects a value the
        ticket states (`labels.spec_mismatch`); None otherwise."""
        if test.failed_filter != 2:
            return None
        return spec_mismatch(test.filters[2][1], self.spec_text)

    def gate_refusals(self) -> list[GateRefusal]:
        """Every refused 'done', in order, per phase: the failed items of the attempt and what
        followed ("passed on attempt 2", "still refused on attempt 2", "no further attempt")."""
        final: dict[str, dict[str, Any]] = {}
        for result in self.gates:  # the last result of each gate id is its outcome
            final[str(result["gate_id"])] = result
        done = {
            gid: r
            for gid, r in final.items()
            if not any(i.get("status") == "pending" for i in r.get("items", []))
        }
        by_phase: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for gid, result in done.items():
            by_phase.setdefault(self._gate_phase.get(gid, "build"), []).append((gid, result))
        refusals: list[GateRefusal] = []
        for phase, attempts in by_phase.items():
            for n, (_gid, result) in enumerate(attempts, start=1):
                if result.get("passed"):
                    continue
                failed = [i for i in result.get("items", []) if i.get("status") == "fail"]
                words = (
                    "; ".join(
                        f"{check_short(str(i.get('name')))}: {i.get('detail')}"
                        if i.get("detail")
                        else check_short(str(i.get("name")))
                        for i in failed
                    )
                    or "a gate item failed"
                )
                if n < len(attempts):
                    nxt = attempts[n][1]
                    outcome = (
                        f"passed on attempt {n + 1}"
                        if nxt.get("passed")
                        else f"still refused on attempt {n + 1}"
                    )
                else:
                    outcome = "no further attempt"
                refusals.append(GateRefusal(phase, n, words, outcome))
        return sorted(refusals, key=lambda r: list(by_phase).index(r.phase))

    def secondary_parts(self) -> list[str]:
        """The full verdict's secondary results, one item each ("hidden tests 50/52", "mutants
        killed 3/4", ...), leaving out the one the primary measure already shows."""
        if self.verdict is None:
            return []
        text = str(self.verdict.get("summary", "")).split("; ")[-1]
        match = re.fullmatch(r"(hidden tests \S+), (mutants killed \S+), (.+)", text)
        parts = list(match.groups()) if match else [text]
        view = self.primary_view
        shown = measure_values(view["values"]) if view and view["values"] else ""
        return [p for p in parts if p and p != shown]

    def files_by_category(self) -> list[tuple[str, list[FileRead]]]:
        """Files-read map: categories in a fixed order (map first), files in read order."""
        groups: dict[str, list[FileRead]] = {}
        for entry in self.files_read.values():
            groups.setdefault(entry.category, []).append(entry)
        order = {name: i for i, name in enumerate(CATEGORY_ORDER)}
        return sorted(groups.items(), key=lambda kv: order.get(kv[0], len(order)))

    def filter_counts(self, number: int) -> tuple[int, int]:
        """(passed, reached) for one test filter across proposed tests."""
        results = [t.filters[number][0] for t in self.tests.values() if number in t.filters]
        return sum(results), len(results)

    def turns(self) -> list[TimelineRow]:
        return [row for row in self.timeline if row.kind == "turn"]

    def recent(self, n: int = RECENT_TURNS) -> list[TimelineRow]:
        """The last `n` turns, with every session marker (stop, resume) kept in log order, so a
        session stop stays visible while the run goes on."""
        turns = [row for row in self.timeline if row.kind == "turn"][-n:]
        first = turns[0].seq if turns else None
        return [
            row
            for row in self.timeline
            if row.kind != "turn" or (first is not None and row.seq >= first)
        ]

    def phase_of(self, session_index: int) -> str:
        """The phase a session belongs to. Turn events carry no phase, so it comes from the claim
        events' `phase` field and the session markers: "test" for a session with a test-phase
        claim, or a later session that started without a session_resume (the test phase begins
        after the build claim, in a new session); "build" for session 1 and every resumed session
        (Section 2's session stops)."""
        if session_index in self._claimed_test:
            return "test"
        return "build" if session_index == 1 or session_index in self._resumed else "test"

    def diff_map(self) -> dict[str, str]:
        """path -> "changed" | "blocked" | "reverted" | "out of scope" (referee wins)."""
        result: dict[str, str] = {}
        for row in self.turns():
            for tool in row.tools:
                for path in tool.files_changed:
                    result[path] = "changed"
        for item in self.blocked:
            label = "reverted" if item["action"] == "revert" else "blocked"
            for path in item["paths"]:
                result.setdefault(path, label)
        for path in self._out_of_scope():
            result[path] = "out of scope"
        return dict(sorted(result.items()))

    def _out_of_scope(self) -> list[str]:
        scope = self.checks.get("diff_scope")
        if not scope:
            return []
        paths: list[str] = []
        for finding in scope.get("findings", []):
            detail = str(finding.get("detail", ""))
            match = re.search(r"out of scope:\s*(\S+)", detail)
            if match and not finding.get("baseline"):
                paths.append(match.group(1))
        return paths

    def sessions(self) -> list[SessionSummary]:
        summaries: dict[int, SessionSummary] = {}
        seen: set[str] = set()
        for row in self.timeline:
            summary = summaries.setdefault(
                row.session_index,
                SessionSummary(row.session_index, phase=self.phase_of(row.session_index)),
            )
            if row.kind != "turn":
                continue
            summary.turns += 1
            for tool in row.tools:
                for path in tool.files_changed:
                    if path not in summary.files:
                        summary.files.append(path)
        for index in sorted(summaries):
            summary = summaries[index]
            summary.ended_by = self._session_ends.get(index, "")
            # The harness's own files (progress.md, the handoff, exec plans, feature_list.json) are
            # meant to change every session: never redone work. The referee strips the same list
            # (`ab.artifacts`) before its continuity measure.
            summary.redone = [p for p in summary.files if p in seen and not is_harness_artifact(p)]
            seen.update(summary.files)
        return [summaries[i] for i in sorted(summaries)]

    def first_wrong_turn(self) -> WrongTurn | None:
        """Heuristic: the earliest turn that edited a file a failing referee check names; else the
        earliest turn with a blocked change, a sandbox denial, or a failed gate."""
        flagged: list[tuple[str, str]] = []  # (text, check label)
        for name, check in self.checks.items():
            if check.get("passed"):
                continue
            for finding in check.get("findings", []):
                if not finding.get("baseline"):
                    label = check_label(str(finding.get("rule") or name))
                    flagged.append(
                        (f"{finding.get('detail', '')} {finding.get('endpoint') or ''}", label)
                    )
        for row in self.turns():
            for tool in row.tools:
                for path in [
                    *tool.files_changed,
                    *([tool.target] if tool.name in _EDIT_TOOLS else []),
                ]:
                    for text, label in flagged:
                        if path and path in text:
                            return WrongTurn(
                                row.session_index,
                                row.turn,
                                row.seq,
                                f"edited {path}, named by the referee ({label})",
                            )
        for row in self.turns():
            if row.flags:
                return WrongTurn(row.session_index, row.turn, row.seq, ", ".join(row.flags))
        return None

    # -- folding --------------------------------------------------------------------------------
    def _current_turn(self) -> TimelineRow | None:
        for row in reversed(self.timeline):
            if row.kind == "turn":
                return row
        return None

    def _flag(self, flag: str, detail: str = "") -> None:
        row = self._current_turn()
        if row is not None and flag not in row.flags:
            row.flags.append(flag)
            if detail:
                row.notes.append(detail)

    def apply(self, event: Event) -> None:  # one branch per event type
        data, kind = event.data, event.type
        if kind == "run_start":
            self.run_start = data
            self._seen["launch"] = (event.seq, event.ts)
        elif kind == "sandbox_start":
            self.sandbox = data
        elif kind == "sandbox_usage":
            self.usage = data
        elif kind == "sandbox_denied":
            self.denials.append(data)
            self._flag("denied", f"sandbox denied ({data['reason_code']}): {data['command']}")
        elif kind == "turn":
            self.session_index = data["session_index"]
            self.timeline.append(
                TimelineRow(
                    kind="turn",
                    seq=event.seq,
                    session_index=data["session_index"],
                    turn=data["turn"],
                    turns_left=data["turns_left"],
                    message=data["message_excerpt"],
                    input_tokens=data["input_tokens"],
                    output_tokens=data["output_tokens"],
                )
            )
        elif kind == "tool_call":
            line = ToolLine(data["call_id"], data["name"], data["target"])
            self._calls[line.call_id] = line
            row = self._current_turn()
            if row is not None:
                row.tools.append(line)
            if line.name == "read_file":
                entry = self.files_read.setdefault(
                    line.target, FileRead(line.target, categorise(line.target))
                )
                entry.count += 1
        elif kind == "tool_result":
            line = self._calls.get(data["call_id"])
            if line is not None:
                line.ok = data["ok"]
                line.exit_code = data["exit_code"]
                line.files_changed = list(data["files_changed"])
                line.output_excerpt = data["output_excerpt"]
        elif kind == "harness_decision":
            self.decisions.append(
                Decision(
                    event.seq, data["kind"], data["layer"], data["message"], list(data["paths"])
                )
            )
            if data["kind"] == "note" and data["message"]:
                row = self._current_turn()
                if row is not None:
                    row.notes.append(data["message"])
            elif data["kind"] == "gate_fail":
                self._flag("gate_fail", f"gate failed: {data['message']}")
        elif kind == "blocked":
            self.blocked.append(data)
            self.decisions.append(
                Decision(event.seq, "blocked", "scope", data["reason"], list(data["paths"]))
            )
            self._flag("blocked", f"blocked ({data['action']}): {', '.join(data['paths'])}")
        elif kind == "session_stop":
            self._session_ends[data["session_index"]] = data["ended_by"]
            self.timeline.append(
                TimelineRow(
                    kind="session_stop",
                    seq=event.seq,
                    session_index=data["session_index"],
                    detail=f"ended by {data['ended_by']}"
                    + (f"; handoff {data['handoff_path']}" if data["handoff_path"] else ""),
                )
            )
        elif kind == "session_resume":
            self.session_index = data["session_index"]
            self._resumed.add(data["session_index"])
            self.timeline.append(
                TimelineRow(
                    kind="session_resume",
                    seq=event.seq,
                    session_index=data["session_index"],
                    detail="prefix: " + ", ".join(data["prefix_blocks"]),
                )
            )
        elif kind == "test_proposed":
            self.tests.setdefault(data["test_id"], TestRow(data["test_id"], data["phase"]))
        elif kind == "test_filter_result":
            row = self.tests.setdefault(data["test_id"], TestRow(data["test_id"], "test"))
            row.filters[int(data["filter"])] = (bool(data["passed"]), data["reason"])
        elif kind == "check_progress":
            self.progress[data["check"]] = data
        elif kind == "check_result":
            self.checks[data["check"]] = data
        elif kind == "mutant_result":
            self.mutants = [
                m
                for m in self.mutants
                if (m["mutant_id"], m["set"]) != (data["mutant_id"], data["set"])
            ]
            self.mutants.append(data)
        elif kind == "reviewer_output":
            self.reviewer = data
        elif kind == "gate_result":
            self.gates.append(data)
            self._gate_phase.setdefault(str(data["gate_id"]), self.phase_of(self.session_index))
        elif kind == "claim":
            self.claims[data["phase"]] = data
            if data["phase"] == "test":
                self._claimed_test.add(self.session_index)
            if data.get("gate_id"):
                self._gate_phase[str(data["gate_id"])] = data["phase"]
        elif kind == "primary_verdict":
            self.primary = data
            self._seen["primary"] = (event.seq, event.ts)
        elif kind == "verdict":
            self.verdict = data
            self._seen["verdict"] = (event.seq, event.ts)
        elif kind == "cost":
            if data["scope"] != "review" or self.cost is None:
                self.cost = data
        elif kind == "screenshot":
            self.screenshots[data["view"]] = data
        elif kind == "trace_link":
            self.traces[data["kind"]] = data["url"]
        elif kind == "run_end":
            self.run_end = data


def summarise(event: Event) -> str:
    """One readable line per event for the live tail."""
    d = event.data
    match event.type:
        case "turn":
            return f"turn {d['session_index']}.{d['turn']}: {d['message_excerpt']}"
        case "tool_call":
            return f"{d['name']} {d['target']}"
        case "tool_result":
            status = "ok" if d["ok"] else f"failed (exit {d['exit_code']})"
            return f"result {status}" + (
                f": {', '.join(d['files_changed'])}" if d["files_changed"] else ""
            )
        case "harness_decision":
            return f"{d['layer']} {d['kind']}" + (f": {d['message']}" if d["message"] else "")
        case "blocked":
            return f"BLOCKED {d['action']}: {', '.join(d['paths'])}"
        case "sandbox_denied":
            return f"DENIED {d['reason_code']}: {d['command']}"
        case "sandbox_start":
            return f"container {d['container_id']} network {d['network']}"
        case "sandbox_usage":
            return f"cpu {d['cpu_pct']:.0f}% mem {d['mem_mb']:.0f}/{d['mem_limit_mb']:.0f} MB"
        case "session_stop":
            return f"session {d['session_index']} stopped ({d['ended_by']})"
        case "session_resume":
            return f"session {d['session_index']} resumed"
        case "test_proposed":
            return f"test proposed {d['test_id']}"
        case "test_filter_result":
            outcome = "pass" if d["passed"] else "discard"
            return f"{filter_name(int(d['filter']))}, {outcome}: {d['test_id']}"
        case "check_progress":
            return progress_label(str(d.get("check", "")), str(d["label"]))
        case "check_result":
            outcome = "pass" if d["passed"] else "fail"
            return f"{check_label(d['check'])}, {outcome} ({d['new_violations']} new)"
        case "mutant_result":
            return f"mutant {d['mutant_id']} {d['outcome']}"
        case "reviewer_output":
            return f"reviewer {d['verdict']}"
        case "gate_result":
            return f"gate {d['gate_id']} {'pass' if d['passed'] else 'fail'}"
        case "claim":
            return f"claim {d['phase']}: {d['claim']}"
        case "primary_verdict":
            outcome = "pass" if d["passed"] else "fail"
            return (
                f"primary verdict {outcome} after {d['elapsed_s']:.0f}s "
                f"({measure_values(d['values'])})"
            )
        case "verdict":
            return f"verdict {'pass' if d['passed_primary'] else 'fail'}: {d['summary']}"
        case "cost":
            return f"cost ${d['run_usd']:.3f} of ${d['limit_usd']:.2f} ({d['scope']})"
        case "screenshot":
            return f"screenshot {d['view']} as {d['as_user']}"
        case "trace_link":
            return f"trace {d['kind']}"
        case "run_end":
            return f"run end {d['status']}"
        case "run_start":
            feature = str(d["spec"].get("feature_id") or "")
            return f"run start {feature_label(feature) if feature else ''}".strip()
    return event.type


@dataclass
class ConsoleState:
    arms: dict[str, ArmState] = field(default_factory=lambda: {a: ArmState(a) for a in ARMS})
    ab: ArmState = field(default_factory=lambda: ArmState("ab"))
    seq: int = 0
    recorded: bool = False
    unsandboxed: bool = False
    ab_id: str | None = None
    _tail: deque[TailLine] = field(default_factory=lambda: deque(maxlen=TAIL_SIZE))

    @classmethod
    def from_events(cls, events: Iterable[Event]) -> ConsoleState:
        state = cls()
        state.extend(events)
        return state

    def extend(self, events: Iterable[Event]) -> int:
        count = 0
        for event in events:
            self.apply(event)
            count += 1
        return count

    def arm(self, name: str) -> ArmState:
        return self.arms.get(name) or ArmState(name)

    def _specs(self) -> list[dict[str, Any]]:
        starts = [a.run_start for a in self.arms.values() if a.run_start]
        return [s["spec"] for s in starts if isinstance(s.get("spec"), dict)]

    @property
    def profile(self) -> str | None:
        """The run profile from the run_start spec (the same for both arms); None before."""
        for spec in self._specs():
            if spec.get("profile"):
                return str(spec["profile"])
        return None

    @property
    def feature(self) -> str | None:
        """The feature code from the run_start spec (the same for both arms); None before."""
        for spec in self._specs():
            if spec.get("feature_id"):
                return str(spec["feature_id"])
        return None

    @property
    def feature_label(self) -> str | None:
        """'Feature 4: Version checks on issue edits', for the screen headers."""
        return feature_label(self.feature) if self.feature else None

    @property
    def single_arm(self) -> bool:
        """The harness arm runs alone (`make show-N`, harness in action): no bare arm starts."""
        return any(bool(spec.get("single_arm")) for spec in self._specs())

    def not_run(self, arm: str) -> str | None:
        """'Not run (harness in action)' for the bare arm of a single-arm run (and 'Not run
        (constructed example)' for a constructed one): the screens show it instead of an empty
        or default result. None for an arm that runs."""
        if arm != "bare":
            return None
        if self.constructed:
            return "Not run (constructed example)"
        return "Not run (harness in action)" if self.single_arm else None

    @property
    def started(self) -> list[ArmState]:
        return [a for a in self.arms.values() if a.run_start is not None]

    @property
    def started_on(self) -> str | None:
        """The day (YYYY-MM-DD, UTC) the run started: the earliest run_start time stamp."""
        stamps = [a._seen["launch"][1] for a in self.started if "launch" in a._seen]
        return min(stamps)[:10] if stamps else None

    @property
    def finished(self) -> bool:
        """Every arm that started has ended and has its full verdict (the referee is done)."""
        arms = self.started
        return bool(arms) and all(
            a.run_end is not None and a.verdict is not None and not a.secondary_pending
            for a in arms
        )

    @property
    def constructed(self) -> bool:
        """A constructed example (`make example-N`): scripted steps drive the harness arm, no
        model; every screen says so."""
        return any(bool(spec.get("constructed")) for spec in self._specs())

    def apply(self, event: Event) -> None:
        self.seq = max(self.seq, event.seq)
        self.ab_id = self.ab_id or event.ab_id
        self.recorded = self.recorded or event.recorded
        if event.type == "sandbox_start" and event.data.get("unsandboxed"):
            self.unsandboxed = True
        target = self.arms.get(event.arm) if event.arm else self.ab
        if target is not None:
            target.apply(event)
        self._tail.append(
            TailLine(event.seq, event.ts, event.arm, event.type, summarise(event), event.recorded)
        )

    def tail(self, n: int = 20) -> list[TailLine]:
        return list(reversed(self._tail))[:n]
