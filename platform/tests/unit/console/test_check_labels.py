"""Referee checks that still showed a code name read as a plain label with the code in brackets
(owner, 2026-10-18): on every console screen and in the terminal. Event payloads, ScoreRecord
JSON, exports, and ab.json keep the codes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from shipharness.console.labels import check_label, check_short, progress_label
from shipharness.console.report import load_report
from shipharness.console.screens import ScreenContext, ScreenRenderer
from shipharness.console.state import ConsoleState
from shipharness.datasets.names import REFEREE_CHECK_NAMES, referee_check_label
from shipharness.events import read_events
from tests.unit.console.fixture_log import AB_ID, build_fixture_exports, build_fixture_run

PLAIN = {
    "diff_scope": "Files outside the allowed paths (diff_scope)",
    "continuity": "Session continuity (continuity)",
    "flakiness": "Flaky tests (flakiness)",
    "regression": "Existing tests (regression)",
}


@pytest.mark.parametrize(("code", "label"), PLAIN.items())
def test_each_referee_check_has_a_plain_label_with_its_code(code: str, label: str) -> None:
    assert referee_check_label(code) == label
    assert check_label(code) == label and check_short(code) == label
    assert code in REFEREE_CHECK_NAMES


def test_gate_item_names_and_finding_rules_map_to_the_same_label() -> None:
    # Gate items carry the runner's short names (checkrun.CHECK_LABELS); findings carry rules.
    assert check_short("existing tests") == PLAIN["regression"]
    assert check_short("diff scope") == PLAIN["diff_scope"]
    assert check_label("scope") == PLAIN["diff_scope"]
    assert check_label("flaky") == PLAIN["flakiness"]
    assert referee_check_label("something else") == "something else"
    assert check_short("hidden_tests") == "hidden tests"  # already plain


def test_progress_labels_name_the_check_plainly() -> None:
    assert progress_label("flakiness", "flakiness run 5/5") == "Flaky tests (flakiness), run 5/5"
    assert progress_label("continuity", "continuity") == PLAIN["continuity"]
    assert progress_label("regression", "existing tests") == PLAIN["regression"]
    assert progress_label("R1", "House rule 1 probes 37/112") == "House rule 1 probes 37/112"
    assert progress_label("hidden_tests", "hidden tests") == "hidden tests"


def test_screens_show_the_plain_labels(tmp_path: Path) -> None:
    state = ConsoleState.from_events(read_events(build_fixture_run(tmp_path / "runs")))
    state.arm("harness").progress["flakiness"] = {
        "check": "flakiness",
        "done": 5,
        "total": 5,
        "label": "flakiness run 5/5",
    }
    exports = build_fixture_exports(tmp_path / "exports")
    screens = ScreenRenderer().render_all(
        ScreenContext(AB_ID, state, load_report(exports), str(exports))
    )
    live = screens["1"]
    assert '<span class="label">Existing tests (regression)</span>' in live
    assert "Flaky tests (flakiness), run 5/5" in live and "flakiness run 5/5" not in live
    evidence = screens["3"]
    # Screen 3: one row per check, the name as text (it may wrap), the result on a short pill.
    assert re.search(
        r'<li class="check-row" title="Files outside the allowed paths \(diff_scope\): \d+ probes">'
        r'<span class="check-name">Files outside the allowed paths \(diff_scope\)</span> '
        r'<span class="status tone-bad"><span class="sym"[^>]*>✗</span> '
        r'<span class="label">1 new</span></span></li>',
        evidence,
    )
    assert "diff_scope, 1 new" not in evidence
    state.arm("harness").checks.clear()  # the referee is still running: screen 3 shows progress
    evidence = ScreenRenderer().render_all(
        ScreenContext(AB_ID, state, load_report(exports), str(exports))
    )["3"]
    assert '<span class="check-name">Flaky tests (flakiness), run 5/5</span>' in evidence


def test_shipharness_check_prints_the_plain_label() -> None:
    from shipharness.checks.commands import _named

    assert _named("diff_scope") == PLAIN["diff_scope"]
    assert _named("r1_tenant") == "r1_tenant (House rule 1: Tenant isolation)"
