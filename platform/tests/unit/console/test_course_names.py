"""The console names house rules, test filters, and sections as "<Kind> N: <name>": the referee
check pills, the gate pills (short form, full name in the tooltip), the filter table, the evidence
panels, the live tail, and the first wrong turn. Event payloads keep the machine ids."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from shipharness.console.labels import check_label, check_short, filter_name, measure_label
from shipharness.console.report import load_report
from shipharness.console.screens import ScreenContext, ScreenRenderer, status
from shipharness.console.state import ConsoleState, measure_values, summarise
from shipharness.events import read_events
from tests.unit.console.fixture_log import AB_ID, build_fixture_exports, build_fixture_run


@pytest.fixture
def state(tmp_path: Path) -> ConsoleState:
    return ConsoleState.from_events(read_events(build_fixture_run(tmp_path / "runs")))


@pytest.fixture
def screens(tmp_path: Path, state: ConsoleState) -> dict[str, str]:
    exports = build_fixture_exports(tmp_path / "exports")
    ctx = ScreenContext(AB_ID, state, load_report(exports), str(exports))
    return ScreenRenderer().render_all(ctx)


def test_check_labels_name_the_house_rule() -> None:
    assert check_label("r1_tenant") == "House rule 1: Tenant isolation"
    assert check_label("R4") == "House rule 4: Safe retries"
    assert check_label("r7_migrations") == "House rule 7: Migrations"
    assert check_short("r6_layering") == "House rule 6"
    assert check_short("R2") == "House rule 2"
    assert check_label("visible tests") == "visible tests" == check_short("visible tests")
    # Referee checks by a plain label with the check name in brackets (owner, 2026-10-18).
    assert check_label("diff_scope") == "Files outside the allowed paths (diff_scope)"
    assert check_short("regression") == "Existing tests (regression)"
    # Plainer pill names (owner, 2026-10-18); the full label keeps the check name.
    assert check_short("hidden_tests") == "hidden tests" and check_short("board") == "board check"


def test_filter_and_measure_names() -> None:
    assert filter_name(3) == "Filter 3: Adds coverage or catches a mutant"
    assert filter_name(9) == "Filter 9"  # a number the course does not name
    assert measure_label("r1_new_violations") == "House rule 1: Tenant isolation, new violations"
    assert measure_label("hidden_passed") == "hidden tests passed"
    assert measure_label("something_else") == "something_else"
    assert measure_values({"r1_new_violations": 2}) == (
        "House rule 1: Tenant isolation, new violations 2"
    )


def test_status_pill_takes_a_tooltip() -> None:
    pill = status("pass", "House rule 1", title="House rule 1: Tenant isolation")
    assert 'title="House rule 1: Tenant isolation"' in pill
    assert '<span class="label">House rule 1</span>' in pill
    assert "title=" not in status("pass", "x")


def test_gate_pills_use_the_short_form_with_the_full_name_in_the_tooltip(
    screens: dict[str, str],
) -> None:
    live = screens["1"]
    assert re.search(
        r'<span class="status tone-good" title="House rule 1: Tenant isolation[^"]*">'
        r'<span class="sym"[^>]*>✓</span>\s*<span class="label">House rule 1</span>',
        live,
    )
    assert '<span class="label">House rule 2</span>' in live
    assert '<span class="label">visible tests</span>' in live  # not a house rule: unchanged
    assert (
        '<span class="label">R1</span>' not in live and '<span class="label">R2</span>' not in live
    )


def test_progress_pills_carry_the_full_rule_name(screens: dict[str, str]) -> None:
    assert re.search(
        r'<span class="progress" title="House rule 1: Tenant isolation">House rule 1 probes',
        screens["1"],
    )


def test_referee_check_pills_name_the_house_rule(screens: dict[str, str]) -> None:
    evidence = screens["3"]
    assert re.search(
        r'title="House rule 1: Tenant isolation: 112 probes">'
        r'<span class="check-name">House rule 1</span> .*?<span class="label">3 new</span>',
        evidence,
    )
    assert re.search(
        r'title="House rule 4: Safe retries: 20 probes">'
        r'<span class="check-name">House rule 4</span> .*?<span class="label">1 new</span>',
        evidence,
    )
    assert '<span class="check-name">Files outside the allowed paths (diff_scope)</span>' in (
        evidence
    )
    assert "r1_tenant" not in evidence and "r4_idempotency" not in evidence


def test_evidence_panels_are_named_after_the_sections(screens: dict[str, str]) -> None:
    evidence = screens["3"]
    headings = re.findall(r"<h2>(.*?)</h2>", evidence)
    assert headings == [
        "Section 1: Instructions · Section 2: State and sessions",
        "Section 3: Scope and sandbox",
        "Section 4: Verification",
    ]


def test_filter_table_names_each_filter(screens: dict[str, str], state: ConsoleState) -> None:
    evidence = screens["3"]
    for number, name in (
        (1, "Builds and collects"),
        (2, "Passes five runs"),
        (3, "Adds coverage or catches a mutant"),
        (4, "Real assertions"),
        (5, "No source changes"),
    ):
        assert f'<th title="Filter {number}: {name}">{number}</th>' in evidence
    assert "Coverage (Filter 3: Adds coverage or catches a mutant): 2 of 2 tests" in evidence
    assert "Filter 4: Real assertions (mocks the unit under test)" in evidence
    mocked = state.arm("harness").tests["tests/test_labels.py::test_label_with_mocks"]
    assert mocked.discard_reason == "Filter 4: Real assertions (mocks the unit under test)"
    assert "(filter 3:" not in evidence and "Test filters 1 to 5" in evidence


def test_live_tail_and_first_wrong_turn_name_rules_and_filters(
    tmp_path: Path, state: ConsoleState
) -> None:
    lines = [summarise(event) for event in read_events(build_fixture_run(tmp_path / "again"))]
    assert "House rule 1: Tenant isolation, fail (3 new)" in lines
    assert "Files outside the allowed paths (diff_scope), fail (1 new)" in lines
    assert any(line.startswith("Filter 4: Real assertions, discard: tests/") for line in lines)
    assert any(line.startswith("Filter 1: Builds and collects, pass: tests/") for line in lines)
    wrong = state.arm("bare").first_wrong_turn()
    assert wrong is not None
    assert not re.search(r"\(R[1-8]\)", wrong.reason)
