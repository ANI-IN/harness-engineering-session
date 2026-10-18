"""Running a constructed example: the A/B machinery with the harness arm alone, a scripted client,
no reviewer, no tracing, and a cost tracker of its own (scripted steps cost $0).

It never goes through the live-client guard of `shipharness ab`: that guard stays in front of every
live run, and a live run can still never use a scripted client.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from shipharness.ab.demo import ABDeps, ABResult, ABTask, ClientFactory, run_ab, section_layers
from shipharness.config import Prices, Settings
from shipharness.console.labels import check_label
from shipharness.console.state import measure_values
from shipharness.cost import Caps, CostTracker
from shipharness.events import Arm, Event, read_events
from shipharness.examples.base import NO_USAGE, Scenario
from shipharness.runner.model import ModelResponse, ScriptedModelClient, Step, text_step
from shipharness.tracing import NullTracer

# The gate and the session-end checks of a scripted run take longer than the class runs' harness
# time limit allows (the visible suite alone takes about a minute); a constructed example is not
# a measurement, so it gets room to show every step.
EXAMPLE_HARNESS_TIMEOUT_S = 1800
EXAMPLE_LEDGER = "example-ledger.jsonl"  # in the run directory, apart from the class ledger


def example_task(scenario: Scenario, task: ABTask) -> ABTask:
    """The section's canonical task, with the scenario's session budget when it sets one."""
    if scenario.session_budget is None:
        return task
    return dataclasses.replace(task, session_budget=list(scenario.session_budget))


def example_settings(settings: Settings) -> Settings:
    """No LangSmith tracing, and the harness time limit raised for the scripted gate runs."""
    timeout = max(settings.harness_timeout_s, EXAMPLE_HARNESS_TIMEOUT_S)
    return settings.model_copy(update={"langsmith_tracing": False, "harness_timeout_s": timeout})


class ExampleClient(ScriptedModelClient):
    """A scripted client whose script, once used up, answers with text and no tokens (the base
    client's fallback reports token usage, which would cost money on paper)."""

    def respond(self, input_items: Any, tools: Any, **kwargs: Any) -> ModelResponse:
        if not self.steps:
            self.steps.append(quiet_step())
        return super().respond(input_items, tools, **kwargs)


def quiet_step() -> Step:
    """A text-only answer with no tokens: two in a row end the session (no tool call)."""
    return dataclasses.replace(text_step("(end of the scripted steps)"), usage=NO_USAGE)


def scripted_client_factory(scenario: Scenario) -> ClientFactory:
    """A fresh scripted client per run; a constructed example has no bare arm."""

    def factory(arm: Arm) -> ScriptedModelClient:
        if arm != "harness":
            raise ValueError("a constructed example drives the harness arm only")
        return ExampleClient(scenario.steps())

    return factory


def example_cost(settings: Settings, ledger: Path) -> CostTracker:
    """A cost tracker with its own ledger: the scripted steps report no tokens, so every entry is
    $0, and nothing is added to the class ledger or counted against its caps."""
    return CostTracker(
        Prices.load(settings.prices_file),
        Caps.from_settings(settings),
        ledger,
        session_id="example",
    )


def run_example(
    scenario: Scenario,
    task: ABTask,
    deps: ABDeps,
    *,
    cost: CostTracker | None = None,
    ab_id: str | None = None,
) -> ABResult:
    """The harness arm with the section's layers on `task`, driven by the scenario's steps, judged
    by the referee, and marked constructed (run_start spec, ab.json, ScoreRecord)."""
    deps = dataclasses.replace(
        deps,
        client_factory=scripted_client_factory(scenario),
        reviewer=None,  # the reviewer is a model call
        tracer=NullTracer(),
        cost=cost or deps.cost,
    )
    return run_ab(
        task,
        section_layers(scenario.section),
        deps,
        ab_id=ab_id,
        section=scenario.section,
        arms=("harness",),
        constructed=True,
    )


def _shown(event: Event) -> str | None:
    """One line for the events that show what the layers and the referee did."""
    d = event.data
    if event.type == "harness_decision":
        if d["kind"] == "note" and str(d["message"]).startswith("agent read"):
            return f"{d['layer']}: {d['message']}"
        if d["kind"] in ("gate_fail", "gate_pass"):
            text = str(d["message"]).splitlines()
            detail = " | ".join(line.strip() for line in text[:2])
            return f"verify: {'GATE FAIL' if d['kind'] == 'gate_fail' else 'GATE PASS'}: {detail}"
        if d["kind"] == "session_stop":
            return f"state: {d['message']}"
        return None
    if event.type == "blocked":
        return f"scope: BLOCKED {', '.join(d['paths'])}: {d['reason']}"
    if event.type == "sandbox_denied":
        return f"sandbox: DENIED {d['reason_code']}: {d['command']} ({d['detail']})"
    if event.type == "session_stop":
        return f"runner: session {d['session_index']} stopped ({d['ended_by']})"
    if event.type == "session_resume":
        return f"runner: session {d['session_index']} resumed"
    if event.type == "claim":
        return f"agent: finish({d['claim']}) in the {d['phase']} phase"
    if event.type == "check_result" and not d["passed"]:
        findings = [f for f in d["findings"] if not f.get("baseline")]
        first = f": {findings[0]['severity']} {findings[0]['detail']}" if findings else ""
        return f"referee: {check_label(d['check'])}, {d['new_violations']} new{first}"[:200]
    if event.type == "primary_verdict":
        outcome = "PASS" if d["passed"] else "FAIL"
        return f"referee: primary verdict {outcome} ({measure_values(d['values'])})"
    return None


def summary_lines(run_dir: Path) -> list[str]:
    """What the layers and the referee did, in order, from the run log."""
    lines = []
    for event in read_events(run_dir / "events.jsonl"):
        line = _shown(event)
        if line:
            lines.append(line)
    return lines


def example_cost_line(cost: CostTracker) -> str:
    total = cost.summary().batch_total_usd
    return f"Cost: ${total:.6f} (constructed example: scripted steps, no model calls)"
