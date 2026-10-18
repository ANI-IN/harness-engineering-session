from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import Caps, CostTracker, Usage
from shipharness.events import EventBus, read_events
from shipharness.harness.base import BaseLayer, Harness, LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import (
    ScriptedModelClient,
    Step,
    classify_openai_error,
    text_step,
    tool_step,
)
from shipharness.runner.models import AgentRunSpec
from shipharness.runner.prompts import NEUTRAL_RESUME, NEUTRAL_WRAPUP, REMINDER
from shipharness.sandbox import FakeSandbox
from shipharness.tracing import NullTracer

from .fakes import fake_openai_key

PRICES = Prices.load(DEFAULT_PRICES_FILE)


def spec(tmp_path: Path, **overrides: object) -> AgentRunSpec:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    (ws / "app.py").write_text("x = 1\n", encoding="utf-8")
    base = dict(
        run_id="r-1",
        arm="bare",
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="Add a list endpoint.",
        model="gpt-6-luna",
        reasoning_effort="low",
        phases=("build",),
        session_budget=[10],
        cost_limit_usd=0.20,
        workspace=ws,
    )
    base.update(overrides)
    return AgentRunSpec(**base)  # type: ignore[arg-type]


def run(
    tmp_path: Path,
    steps: list[Step],
    *,
    harness: Harness | None = None,
    caps: Caps | None = None,
    options: RunOptions | None = None,
    **spec_overrides: object,
):  # type: ignore[no-untyped-def]
    client = ScriptedModelClient(steps)
    tracker = CostTracker(
        PRICES,
        caps or Caps(run=0.20, review=0.04, session=2.5, batch=2.5, experiment=25.0),
        tmp_path / "ledger.jsonl",
        session_id="test",
    )
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        result = run_agent(
            spec(tmp_path, **spec_overrides),
            harness or Harness([]),
            FakeSandbox(),
            bus,
            tracker,
            NullTracer(),
            client,
            options or RunOptions(wrapup_turns=2, sleep=lambda _s: None),
        )
    return result, list(read_events(log)), client


def types(events) -> list[str]:  # type: ignore[no-untyped-def]
    return [e.type for e in events if e.type != "cost"]


def finish(claim: str = "done", summary: str = "implemented") -> Step:
    return tool_step("finish", claim=claim, summary=summary)


def read_app() -> Step:
    return tool_step("read_file", path="app.py", start_line=None, max_lines=None)


def test_finish_done_completes_the_run(tmp_path: Path) -> None:
    result, events, _ = run(tmp_path, [read_app(), finish()])
    assert result.status == "completed"
    assert result.claim == "done"
    assert result.claim_summary == "implemented"
    assert result.turns_total == 2
    assert types(events) == [
        "run_start",
        "turn",
        "tool_call",
        "tool_result",
        "turn",
        "tool_call",
        "claim",
        "tool_result",
        "run_end",
    ]


def test_text_only_twice_sends_one_reminder_then_claims_none(tmp_path: Path) -> None:
    result, _events, client = run(tmp_path, [text_step("thinking"), text_step("still thinking")])
    assert result.claim == "none"
    reminders = [
        item
        for item in client.inputs[-1]
        if item.get("role") == "user" and REMINDER in str(item.get("content"))
    ]
    assert len(reminders) == 1
    assert result.sessions[-1].ended_by == "no_tool_call"


def test_session_budget_stops_and_resumes_with_fresh_context(tmp_path: Path) -> None:
    steps = [read_app()] * 6
    result, events, client = run(tmp_path, steps, session_budget=[3, 3])
    assert [s.ended_by for s in result.sessions] == ["turn_budget", "turn_budget"]
    assert "session_stop" in types(events) and "session_resume" in types(events)
    first_input, fourth_input = client.inputs[0], client.inputs[3]
    assert fourth_input[0] == first_input[0]  # same stable developer prefix
    assert any(NEUTRAL_RESUME in str(item.get("content")) for item in fourth_input)
    assert not any(item.get("type") == "function_call" for item in fourth_input)


def test_wrapup_message_sent_when_turns_left_equal_wrapup_turns(tmp_path: Path) -> None:
    _result, _events, client = run(tmp_path, [read_app()] * 4, session_budget=[4])
    sent_at = [
        i
        for i, received in enumerate(client.inputs)
        if any(NEUTRAL_WRAPUP in str(item.get("content")) for item in received)
    ]
    assert sent_at[0] == 2  # 4 turns, wrap-up when 2 turns remain


def test_cost_cap_aborts_and_still_ends_the_run(tmp_path: Path) -> None:
    expensive = Usage(input_tokens=1_000, output_tokens=500_000)  # $0.25 per call
    result, events, _ = run(
        tmp_path, [tool_step("list_dir", path=".", depth=None, usage=expensive)]
    )
    assert result.status == "ABORTED: cap"
    assert types(events)[-1] == "run_end"


def test_gate_fail_feedback_is_the_finish_result_and_loop_continues(tmp_path: Path) -> None:
    class Gate(BaseLayer):
        name = "verify"
        calls = 0

        def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
            Gate.calls += 1
            if Gate.calls == 1:
                return HarnessDecision(
                    kind="gate_fail", layer="verify", message="R1: GET /issues leaks"
                )
            return HarnessDecision(kind="gate_pass", layer="verify", message="all checks pass")

    result, _events, client = run(
        tmp_path, [finish(), read_app(), finish()], harness=Harness([Gate()])
    )
    assert result.claim == "done"
    assert result.turns_total == 3
    outputs = [item for item in client.inputs[1] if item.get("type") == "function_call_output"]
    assert "R1: GET /issues leaks" in outputs[-1]["output"]


def test_tool_list_is_identical_every_turn(tmp_path: Path) -> None:
    _result, _events, client = run(tmp_path, [read_app(), read_app(), finish()])
    first = json.dumps(client.tools[0])
    assert all(json.dumps(tools) == first for tools in client.tools)


def test_invalid_json_arguments_become_an_error_result(tmp_path: Path) -> None:
    bad = Step(
        output_items=[
            {
                "type": "function_call",
                "call_id": "c9",
                "name": "read_file",
                "arguments": "{not json",
            }
        ]
    )
    result, _events, client = run(tmp_path, [bad, finish()])
    assert result.status == "completed"
    outputs = [item for item in client.inputs[1] if item.get("type") == "function_call_output"]
    assert "invalid arguments" in outputs[0]["output"]


class FakeAPIError(Exception):
    def __init__(
        self, status_code: int | None, code: str | None = None, message: str | None = None
    ) -> None:
        super().__init__(message or f"status {status_code}")
        self.status_code = status_code
        self.code = code


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (FakeAPIError(429, "insufficient_quota"), "abort_billing"),
        (FakeAPIError(429, "credit_balance_exhausted"), "abort_billing"),
        (FakeAPIError(429), "retry"),
        (FakeAPIError(401), "abort_auth"),
        (FakeAPIError(403), "abort_auth"),
        (FakeAPIError(500), "retry"),
        (FakeAPIError(400), "abort_other"),
    ],
)
def test_classify_openai_error(exc: Exception, expected: str) -> None:
    assert classify_openai_error(exc) == expected


def test_rate_limit_is_retried_with_backoff(tmp_path: Path) -> None:
    sleeps: list[float] = []
    steps = [Step(error=FakeAPIError(429)), Step(error=FakeAPIError(429)), finish()]
    result, _e, _c = run(tmp_path, steps, options=RunOptions(wrapup_turns=2, sleep=sleeps.append))
    assert result.status == "completed"
    assert sleeps == [1.0, 2.0]


def test_auth_error_ends_with_error_naming_the_variable_not_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = fake_openai_key()
    monkeypatch.setenv("OPENAI_API_KEY", key)
    error = FakeAPIError(401, message=f"Incorrect API key provided: {key}")
    assert key in str(error)  # the provider error text carries the key: the check is not vacuous
    result, events, _ = run(tmp_path, [Step(error=error)])
    assert result.status == "ERROR"
    assert result.error is not None and "OPENAI_API_KEY" in result.error
    assert key not in result.error
    assert key not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert types(events)[-1] == "run_end"


def test_harness_hook_exception_ends_run_with_error_and_run_end(tmp_path: Path) -> None:
    class Broken(BaseLayer):
        name = "scope"

        def before_tool(self, ctx: LayerContext, call):  # type: ignore[no-untyped-def]
            raise RuntimeError("layer bug")

    result, events, _ = run(tmp_path, [read_app(), finish()], harness=Harness([Broken()]))
    assert result.status == "ERROR"
    assert result.error is not None and "RuntimeError" in result.error
    assert types(events)[-1] == "run_end"


def test_unknown_model_price_ends_run_with_error_and_run_end(tmp_path: Path) -> None:
    result, events, _ = run(tmp_path, [finish()], model="gpt-unknown")
    assert result.status == "ERROR"
    assert types(events)[-1] == "run_end"


def test_trace_link_is_retried_at_the_end_when_unavailable_at_start(tmp_path: Path) -> None:
    from contextlib import contextmanager

    from shipharness.tracing import RunHandle

    class FlakyTracer(NullTracer):
        calls = 0

        @contextmanager
        def agent_run(self, name, metadata, tags=None, inputs=None):  # type: ignore[no-untyped-def]
            yield RunHandle(object())

        def url(self, handle: RunHandle) -> str | None:
            FlakyTracer.calls += 1
            return None if FlakyTracer.calls == 1 else "https://smith.example/trace/1"

    client = ScriptedModelClient([finish()])
    tracker = CostTracker(
        PRICES,
        Caps(run=0.2, review=0.04, session=2.5, batch=2.5, experiment=25.0),
        tmp_path / "l.jsonl",
        session_id="t",
    )
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        result = run_agent(
            spec(tmp_path),
            Harness([]),
            FakeSandbox(),
            bus,
            tracker,
            FlakyTracer(),
            client,
            RunOptions(sleep=lambda _s: None),
        )
    assert result.trace_url == "https://smith.example/trace/1"
    assert [e.data["url"] for e in read_events(log) if e.type == "trace_link"] == [
        "https://smith.example/trace/1"
    ]


# --- M4: claims per phase, last_claim state, handoff path, cost pre-check, error paths ----------


def test_claims_are_recorded_per_phase(tmp_path: Path) -> None:
    steps = [finish("done", "built"), finish("not_done", "no tests")]
    result, _events, _ = run(tmp_path, steps, phases=("build", "test"))
    assert result.claims == {"build": "done", "test": "not_done"}
    assert result.claim == "not_done"  # last finish call, as before


def test_phase_without_finish_has_claim_none(tmp_path: Path) -> None:
    steps = [read_app(), finish("done", "tests written")]
    result, _events, _ = run(tmp_path, steps, phases=("build", "test"), session_budget=[1])
    assert result.claims == {"build": "none", "test": "done"}


def test_last_claim_is_in_layer_state_before_the_gate_runs(tmp_path: Path) -> None:
    seen: list[object] = []

    class Spy(BaseLayer):
        name = "verify"

        def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
            seen.append(dict(ctx.state["last_claim"]))
            return None

        def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
            seen.append(dict(ctx.state["last_claim"]))
            return []

    run(
        tmp_path,
        [finish("not_done", "stuck"), finish("done", "ok")],
        harness=Harness([Spy()]),
        phases=("build", "test"),
    )
    assert seen == [
        {"phase": "build", "claim": "not_done", "summary": "stuck"},
        {"phase": "test", "claim": "done", "summary": "ok"},
        {"phase": "test", "claim": "done", "summary": "ok"},
    ]


def test_session_stop_carries_the_handoff_path_from_layer_state(tmp_path: Path) -> None:
    class State(BaseLayer):
        name = "state"

        def on_session_end(self, ctx: LayerContext, result):  # type: ignore[no-untyped-def]
            ctx.state["state.handoff_path"] = "session-handoff.md"
            return []

    _result, events, _ = run(
        tmp_path, [read_app()] * 4, harness=Harness([State()]), session_budget=[2, 2]
    )
    stops = [e for e in events if e.type == "session_stop"]
    assert [e.data["handoff_path"] for e in stops] == ["session-handoff.md"]


def test_session_stop_handoff_path_is_null_for_the_bare_arm(tmp_path: Path) -> None:
    _result, events, _ = run(tmp_path, [read_app()] * 4, session_budget=[2, 2])
    assert [e.data["handoff_path"] for e in events if e.type == "session_stop"] == [None]


def test_cost_precheck_counts_tool_schema_tokens(tmp_path: Path) -> None:
    from shipharness.runner.loop import estimate_input_tokens
    from shipharness.runner.tools import TOOL_SCHEMAS

    items = [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}]
    schema_chars = len(json.dumps(TOOL_SCHEMAS))
    assert estimate_input_tokens(items, TOOL_SCHEMAS) - estimate_input_tokens(items, []) >= (
        schema_chars // 3
    )

    estimates: list[int] = []

    class Spy(CostTracker):
        def check_before_call(self, scope, model, est_input_tokens, max_output_tokens, *tier):  # type: ignore[no-untyped-def]
            estimates.append(est_input_tokens)
            return super().check_before_call(
                scope, model, est_input_tokens, max_output_tokens, *tier
            )

    client = ScriptedModelClient([finish()])
    tracker = Spy(PRICES, Caps(0.2, 0.04, 2.5, 2.5, 25.0), tmp_path / "l.jsonl", session_id="t")
    with EventBus(tmp_path / "events.jsonl", ab_id=None) as bus:
        run_agent(spec(tmp_path), Harness([]), FakeSandbox(), bus, tracker, NullTracer(), client)
    assert estimates and estimates[0] >= schema_chars // 3


def test_billing_429_aborts_without_retry(tmp_path: Path) -> None:
    sleeps: list[float] = []
    steps = [Step(error=FakeAPIError(429, "insufficient_quota")), finish()]
    result, events, client = run(
        tmp_path, steps, options=RunOptions(wrapup_turns=2, sleep=sleeps.append)
    )
    assert result.status == "ERROR"
    assert result.error is not None and "billing" in result.error
    assert sleeps == []
    assert len(client.inputs) == 1
    assert types(events)[-1] == "run_end"


def test_unknown_tool_name_becomes_an_error_result_and_the_loop_continues(tmp_path: Path) -> None:
    bogus = Step(
        output_items=[
            {"type": "function_call", "call_id": "c7", "name": "delete_repo", "arguments": "{}"}
        ]
    )
    result, events, client = run(tmp_path, [bogus, finish()])
    assert result.status == "completed" and result.claim == "done"
    outputs = [item for item in client.inputs[1] if item.get("type") == "function_call_output"]
    assert "unknown tool" in outputs[0]["output"]
    results = [e for e in events if e.type == "tool_result"]
    assert results[0].data["ok"] is False


def test_non_object_arguments_become_an_error_result(tmp_path: Path) -> None:
    listy = Step(
        output_items=[
            {"type": "function_call", "call_id": "c8", "name": "read_file", "arguments": "[1, 2]"}
        ]
    )
    result, _events, client = run(tmp_path, [listy, finish()])
    assert result.status == "completed"
    outputs = [item for item in client.inputs[1] if item.get("type") == "function_call_output"]
    assert "invalid arguments" in outputs[0]["output"]
    assert "JSON object" in outputs[0]["output"]


def test_text_only_end_after_a_rejected_done_records_claim_none(tmp_path: Path) -> None:
    class Gate(BaseLayer):
        name = "verify"

        def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
            return HarnessDecision(kind="gate_fail", layer="verify", message="R1 fails")

    steps = [finish(), text_step("hmm"), text_step("hmm")]
    result, _events, _ = run(tmp_path, steps, harness=Harness([Gate()]))
    assert result.claims == {"build": "none"}
    assert result.claim == "none"


# --- harness setup commit: placed artifacts never reach the harness arm's diff ----------------

GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@x", "-c", "core.autocrlf=false"]


def _git_repo(tmp_path: Path) -> Path:
    import subprocess

    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (ws / "app.py").write_text("x = 1\n", encoding="utf-8")  # spec() writes it too
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "checkpoint"]):
        subprocess.run(["git", *GIT_ID, *args], cwd=ws, check=True, capture_output=True)
    return ws


class _RepoSandbox(FakeSandbox):
    """Runs the setup commit for real (as the container would) and simulates the agent's edit."""

    def __init__(self, ws: Path) -> None:
        super().__init__()
        self.ws = ws

    def exec(self, command: str, timeout_s: int):  # type: ignore[no-untyped-def]
        import subprocess

        from shipharness.sandbox import ExecResult

        self.commands.append(command)
        if command.startswith("git status --porcelain"):
            import os

            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            done = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.ws, capture_output=True, env=env
            )
            return ExecResult(exit_code=0, output=done.stdout.decode(), duration_ms=1)
        if command.startswith("git add -A"):
            import os

            # Like the container: no global git config (on Windows a global autocrlf would
            # rewrite line endings at commit time).
            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            done = subprocess.run(command, cwd=self.ws, shell=True, capture_output=True, env=env)
            return ExecResult(exit_code=done.returncode, output="", duration_ms=1)
        if command == "make-change":
            (self.ws / "app" / "new.py").write_text("y = 2\n", encoding="utf-8")
            (self.ws / "progress.md").write_text("# Progress\n\nworked\n", encoding="utf-8")
        return ExecResult(exit_code=0, output="", duration_ms=1)


class _Placer(BaseLayer):
    name = "instructions"

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        (ctx.workspace / "AGENTS.md").write_text("# Map\n", encoding="utf-8")
        (ctx.workspace / "progress.md").write_text("# Progress\n", encoding="utf-8")
        return [HarnessDecision(kind="note", layer="instructions", paths=["AGENTS.md"])]


def _run_repo(tmp_path: Path, harness: Harness):  # type: ignore[no-untyped-def]
    ws = _git_repo(tmp_path)
    sandbox = _RepoSandbox(ws)
    steps = [tool_step("run", command="make-change", timeout_s=None), finish()]
    tracker = CostTracker(PRICES, Caps(0.2, 0.04, 2.5, 2.5, 25.0), tmp_path / "l.jsonl", "t")
    with EventBus(tmp_path / "events.jsonl", ab_id=None) as bus:
        result = run_agent(
            spec(tmp_path, workspace=ws),
            harness,
            sandbox,
            bus,
            tracker,
            NullTracer(),
            ScriptedModelClient(steps),
            RunOptions(sleep=lambda _s: None),
        )
    return result, sandbox


def test_harness_arm_diff_excludes_placed_setup_files(tmp_path: Path) -> None:
    result, sandbox = _run_repo(tmp_path, Harness([_Placer()]))
    assert any(c.startswith("git add -A") for c in sandbox.commands)
    assert result.diff_path is not None
    text = result.diff_path.read_text(encoding="utf-8")
    assert "app/new.py" in text
    assert "AGENTS.md" not in text
    assert "+worked" in text  # the agent's own state update is in the diff (referee strips it)


def test_bare_arm_diff_is_against_the_checkpoint_and_no_setup_commit_runs(tmp_path: Path) -> None:
    result, sandbox = _run_repo(tmp_path, Harness([]))
    assert not any(c.startswith("git add -A") for c in sandbox.commands)
    assert result.diff_path is not None
    text = result.diff_path.read_text(encoding="utf-8")
    assert "app/new.py" in text and "progress.md" in text


def test_setup_commit_is_skipped_when_layers_already_committed_everything(
    tmp_path: Path,
) -> None:
    import subprocess

    class CommittingPlacer(BaseLayer):
        name = "state"

        def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
            (ctx.workspace / "progress.md").write_text("# Progress\n", encoding="utf-8")
            subprocess.run(
                ["git", *GIT_ID, "-c", "core.autocrlf=false", "add", "progress.md"],
                cwd=ctx.workspace,
                check=True,
            )
            subprocess.run(
                ["git", *GIT_ID, "commit", "-qm", "state setup"], cwd=ctx.workspace, check=True
            )
            return []

    result, sandbox = _run_repo(tmp_path, Harness([CommittingPlacer()]))
    assert any(c.startswith("git status --porcelain") for c in sandbox.commands)
    assert not any(c.startswith("git add -A") for c in sandbox.commands)
    assert result.diff_path is not None
    text = result.diff_path.read_text(encoding="utf-8")
    assert "app/new.py" in text
    assert "--- /dev/null\n+++ b/progress.md" not in text  # setup version is the diff base


def test_after_tool_revert_reasons_reach_the_agent(tmp_path: Path) -> None:
    class Reverter(BaseLayer):
        name = "scope"

        def after_tool(self, ctx, call, result):  # type: ignore[no-untyped-def]
            return [
                HarnessDecision(
                    kind="revert",
                    layer="scope",
                    message="app/api/middleware.py is outside the build phase's allowed paths",
                    paths=["app/api/middleware.py"],
                )
            ]

    _result, _events, client = run(tmp_path, [read_app(), finish()], harness=Harness([Reverter()]))
    outputs = [item for item in client.inputs[1] if item.get("type") == "function_call_output"]
    assert outputs[0]["output"].endswith(
        "REVERTED: app/api/middleware.py is outside the build phase's allowed paths"
    )


def test_sessions_record_working_tree_snapshots_without_commits(tmp_path: Path) -> None:
    """The bare arm may never commit; session boundaries are still captured as trees."""
    ws = _git_repo(tmp_path)
    sandbox = _RepoSandbox(ws)
    steps = [tool_step("run", command="make-change", timeout_s=None), finish()]
    tracker = CostTracker(PRICES, Caps(0.2, 0.04, 2.5, 2.5, 25.0), tmp_path / "l.jsonl", "t")
    with EventBus(tmp_path / "events.jsonl", ab_id=None) as bus:
        result = run_agent(
            spec(tmp_path, workspace=ws),
            Harness([]),
            sandbox,
            bus,
            tracker,
            NullTracer(),
            ScriptedModelClient(steps),
            RunOptions(sleep=lambda _s: None, snapshot_dir=tmp_path / "snapshots"),
        )
    (session,) = result.sessions
    assert session.start_sha == session.end_sha  # nothing was committed
    assert session.start_tree and session.end_tree and session.start_tree != session.end_tree


# Pilot change (2026-10-17, "bug fix, applies to both arms"): in pilot runs 3 and 4, F2 arms of
# both arms called finish(claim="not_done") at the end of the first of two build sessions, which
# ended the build phase, so the second session never ran. Before the last build session, not_done
# now ends only that session; the next session starts as after a turn budget.


def test_not_done_before_the_last_build_session_ends_only_that_session(tmp_path: Path) -> None:
    steps = [read_app(), finish("not_done", "out of turns"), read_app(), finish()]
    result, events, client = run(tmp_path, steps, session_budget=[3, 3])
    assert [s.ended_by for s in result.sessions] == ["claim_not_done", "claim_done"]
    assert result.status == "completed"
    assert result.claim == "done"
    assert "session_stop" in types(events) and "session_resume" in types(events)
    third_input = client.inputs[2]
    assert any(NEUTRAL_RESUME in str(item.get("content")) for item in third_input)


def test_not_done_in_the_last_build_session_still_ends_the_phase(tmp_path: Path) -> None:
    steps = [read_app(), read_app(), finish("not_done", "cannot finish")]
    result, _events, _ = run(tmp_path, steps, session_budget=[2, 3])
    assert [s.ended_by for s in result.sessions] == ["turn_budget", "claim_not_done"]
    assert result.claim == "not_done"


def test_not_done_in_the_test_phase_ends_the_phase(tmp_path: Path) -> None:
    steps = [finish(), finish("not_done", "no tests")]
    result, _events, _ = run(
        tmp_path, steps, phases=("build", "test"), session_budget=[1, 1], test_phase_turns=3
    )
    assert [(s.phase, s.ended_by) for s in result.sessions] == [
        ("build", "claim_done"),
        ("test", "claim_not_done"),
    ]


def test_the_rule_is_the_same_for_the_harness_arm(tmp_path: Path) -> None:
    class Quiet(BaseLayer):
        name = "state"

    steps = [read_app(), finish("not_done", "out of turns"), read_app(), finish()]
    result, _events, _ = run(
        tmp_path, steps, harness=Harness([Quiet()]), arm="harness", session_budget=[3, 3]
    )
    assert [s.ended_by for s in result.sessions] == ["claim_not_done", "claim_done"]


# --- the visible-test directory comes from the run ----------------------------------------------


def test_teamtrack_runs_keep_the_tests_visible_prompts_tools_and_events(tmp_path: Path) -> None:
    from shipharness.runner.prompts import CORE_SYSTEM_PROMPT, TEST_PHASE
    from shipharness.runner.tools import TOOL_SCHEMAS

    _result, events, client = run(tmp_path, [finish()], phases=("test",))
    assert client.tools[0] == TOOL_SCHEMAS
    developer, user = client.inputs[0][0], client.inputs[0][1]
    assert developer["content"][0]["text"] == CORE_SYSTEM_PROMPT
    assert user["content"][0]["text"].startswith(TEST_PHASE)
    [start] = [e for e in events if e.type == "run_start"]
    assert "visible_tests_dir" not in start.data["spec"]


def test_a_run_with_tests_in_tests_names_that_directory_to_the_agent(tmp_path: Path) -> None:
    _result, events, client = run(tmp_path, [finish()], phases=("test",), visible_tests_dir="tests")
    [tool] = [t for t in client.tools[0] if t["name"] == "run_visible_tests"]
    assert "tests/visible" not in json.dumps(tool)
    developer, user = client.inputs[0][0], client.inputs[0][1]
    assert "tests/visible" not in developer["content"][0]["text"]
    assert "visible test suite in tests." in developer["content"][0]["text"]
    assert "new test files under tests/." in user["content"][0]["text"]
    [start] = [e for e in events if e.type == "run_start"]
    assert start.data["spec"]["visible_tests_dir"] == "tests"


@pytest.mark.parametrize("bad", ["/abs", "../up", "tests/../..", "a b", "x;rm", "", "C:/x"])
def test_visible_tests_dir_must_be_a_plain_relative_directory(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        spec(tmp_path, visible_tests_dir=bad)


def test_visible_tests_dir_drops_a_trailing_slash(tmp_path: Path) -> None:
    assert spec(tmp_path, visible_tests_dir="tests/").visible_tests_dir == "tests"
    assert spec(tmp_path).visible_tests_dir == "tests/visible"
