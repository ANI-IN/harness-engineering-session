"""The agent's claim per phase (owner decision, 2026-10-19): screen 1 and the terminal arm line of
`shipharness ab` both say "agent said: done (build) · not done (test phase)" when the agent made a
claim in the test phase, and just "agent said: done" when it claimed in the build phase only. A
Section 4 run used to say "not done" (the last claim) in the terminal and "done" (the build claim)
on screen 1."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from shipharness.ab.commands import record_line
from shipharness.console.labels import claim_parts, claim_words
from shipharness.console.report import load_report
from shipharness.console.screens import ScreenContext, ScreenRenderer
from shipharness.console.state import ConsoleState
from shipharness.events import EventBus, read_events
from tests.unit.ab.score_fixtures import record
from tests.unit.console.run_logs import LogWriter


@pytest.mark.parametrize(
    ("claims", "words"),
    [
        ({"build": "done"}, "agent said: done"),
        ({"build": "done", "test": "none"}, "agent said: done"),  # test phase, no finish()
        ({"build": "not_done"}, "agent said: not done"),
        ({"build": "done", "test": "not_done"}, "agent said: done (build) · not done (test phase)"),
        ({"build": "done", "test": "done"}, "agent said: done (build) · done (test phase)"),
        ({}, "agent said: no claim"),
        ({"build": "none", "test": "none"}, "agent said: no claim"),
        ({"test": "done"}, "agent said: no claim (build) · done (test phase)"),
        (
            {"build": "none", "test": "not_done"},
            "agent said: no claim (build) · not done (test phase)",
        ),
    ],
)
def test_the_claim_reads_per_phase(claims: dict[str, str], words: str) -> None:
    assert claim_words(claims) == words


def test_the_parts_keep_the_claim_key_for_the_pill_colour() -> None:
    assert claim_parts({"build": "done", "test": "not_done"}) == [
        ("done", "done (build)"),
        ("not_done", "not done (test phase)"),
    ]
    assert claim_parts({"build": "done"}) == [("done", "done")]
    assert claim_parts({}) == [("none", "no claim")]


def test_the_terminal_line_says_the_claim_per_phase() -> None:
    show_4 = record(arm="harness", claim="not_done")  # ScoreRecord.claim stays the last claim
    line = record_line(show_4, {"build": "done", "test": "not_done"})
    assert " agent said: done (build) · not done (test phase) · " in line
    final = record_line(record(arm="bare", claim="done"), {"build": "done", "test": "none"})
    assert " agent said: done · " in final and "(build)" not in final
    assert " agent said: no claim · " in record_line(record(claim="none"))
    assert " agent said: done · " in record_line(record(claim="done"))  # no claims: the record's


def _show_4_log(runs: Path, test_claim: str | None) -> Path:
    log = runs / "ab-20261019-100000-aaaaaa" / "events.jsonl"
    with EventBus(log, ab_id=log.parent.name) as bus:
        w = LogWriter(bus)
        w.start("harness", single_arm=True, feature="F4")
        w.turn("harness", 1, 1, edit="app/services/issues.py")
        w.claim("harness", "build", "done")
        w.turn("harness", 2, 1)
        if test_claim:
            w.claim("harness", "test", test_claim)
        w.end("harness")
        w.judge("harness")
    return log


def _agent_said(log: Path) -> str:
    state = ConsoleState.from_events(read_events(log))
    exports = log.parent.parent / "no-exports"
    ctx = ScreenContext(log.parent.name, state, load_report(exports), str(exports))
    live = ScreenRenderer().render_all(ctx)["1"]
    harness = re.search(r'data-arm="harness">(.*?)</article>', live, flags=re.S)
    assert harness
    line = re.search(r"<p><span class=\"k\">Agent said.*?</p>", harness.group(1), flags=re.S)
    assert line
    return " ".join(re.sub(r"<[^>]+>", " ", line.group(0)).split())


def test_screen_1_says_the_claim_per_phase(tmp_path: Path) -> None:
    text = _agent_said(_show_4_log(tmp_path / "a", "not_done"))
    assert text == "Agent said: ✓ done (build) · ✗ not done (test phase)"


def test_screen_1_keeps_a_build_only_claim_simple(tmp_path: Path) -> None:
    assert _agent_said(_show_4_log(tmp_path / "b", None)) == "Agent said: ✓ done"
