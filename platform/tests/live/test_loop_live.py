"""Live smoke test of the agent loop against the real Responses API (cap $0.02).

Run with: uv run pytest -m live tests/live/test_loop_live.py -s
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shipharness.config import Prices, Settings
from shipharness.cost import Caps, CostTracker
from shipharness.events import EventBus, read_events
from shipharness.harness.base import Harness
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import OpenAIModelClient
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import LocalSandbox, default_policy
from shipharness.tracing import make_tracer

pytestmark = pytest.mark.live


def test_two_turn_run_reads_a_file_and_finishes(tmp_path: Path) -> None:
    settings = Settings()
    if settings.openai_api_key is None:
        pytest.skip("OPENAI_API_KEY is required")
    from openai import OpenAI

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "app.py").write_text("def greet(name):\n    return f'hello {name}'\n", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["add", "."],
        ["-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "checkpoint"],
    ):
        subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True)

    spec = AgentRunSpec(
        run_id="r-live-smoke",
        arm="bare",
        feature_id="SMOKE",
        checkpoint="local",
        ticket_text=(
            'Read app.py. Then call finish with claim="done" and a one-sentence summary '
            "naming the function it defines. Do not change any files."
        ),
        model=settings.openai_model,
        reasoning_effort="low",
        phases=("build",),
        session_budget=[4],
        max_output_tokens=2000,
        cost_limit_usd=0.02,
        workspace=ws,
    )
    tracker = CostTracker(
        Prices.load(settings.prices_file),
        Caps(run=0.02, review=0.04, session=2.5, batch=0.05, experiment=25.0),
        tmp_path / "ledger.jsonl",
        session_id="live-smoke",
    )
    tracer = make_tracer(settings, "shipharness-dev")
    client = OpenAIModelClient(
        tracer.wrap_openai(
            OpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0, timeout=120)
        )
    )
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        result = run_agent(
            spec,
            Harness([]),
            LocalSandbox(default_policy(settings), ws, bus, spec.run_id, "bare"),
            bus,
            tracker,
            tracer,
            client,
            RunOptions(wrapup_turns=1),
        )
    turns = [e for e in read_events(log) if e.type == "turn"]
    print(
        f"\nstatus={result.status} claim={result.claim} turns={result.turns_total} "
        f"cost=${result.cost_usd:.6f} trace={result.trace_url}"
    )
    for t in turns:
        d = t.data
        print(
            f"  turn {d['turn']}: in={d['input_tokens']} cached={d['cached_tokens']} "
            f"write={d['cache_write_tokens']} out={d['output_tokens']} "
            f"reasoning={d['reasoning_tokens']}"
        )
    assert result.status == "completed", result.error
    assert result.claim == "done"
    assert "greet" in result.claim_summary
    assert 1 <= result.turns_total <= 4
    assert 0 < result.cost_usd < 0.02
    if settings.langsmith_api_key is not None:
        assert result.trace_url is not None
    assert all(t.data["input_tokens"] > 0 for t in turns)
    assert (ws / "app.py").read_text(encoding="utf-8").startswith("def greet")
