"""Early primary verdict on screens 1 and 4: a "primary verdict ready" pill with PASS/FAIL and the
primary values as soon as `primary_verdict` arrives, "secondary checks running" until the full
verdict, and the time from launch to each verdict per arm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from shipharness.console.app import create_console_app
from shipharness.console.state import ConsoleState
from shipharness.events import Event
from tests.unit.console.test_screens import screens_of

AB = "ab-early"
RUN = {"bare": "run-b", "harness": "run-h"}
# Launch at 10:00:00; bare's primary verdict at 10:04:10, its full verdict at 10:06:30.
TIMES = {"launch": "10:00:00", "primary": "10:04:10", "verdict": "10:06:30"}


def event(seq: int, arm: str, type_: str, data: dict[str, Any], at: str) -> Event:
    return Event(
        ab_id=AB,
        run_id=RUN[arm],
        arm=arm,  # type: ignore[arg-type]
        seq=seq,
        ts=f"2026-10-17T{at}.000Z",
        type=type_,  # type: ignore[arg-type]
        data=data,
    )


def primary(arm: str, passed: bool, r1: int) -> dict[str, Any]:
    return {
        "arm": arm,
        "run_id": RUN[arm],
        "feature_id": "F1",
        "primary_measure": "r1_new_violations>=1",
        "passed": passed,
        "values": {"r1_new_violations": r1},
        "elapsed_s": 12.5,
    }


def verdict(passed: bool, r1: int) -> dict[str, Any]:
    return {
        "primary": {"r1_new_violations": r1},
        "passed_primary": passed,
        "summary": f"agent said done; referee: {'passes' if passed else 'fails'} the primary "
        f"measure; hidden tests 3/4, mutants killed 1/2, House rule 1: Tenant isolation, "
        f"new violations {r1}",
    }


def events(*, full: bool) -> list[Event]:
    spec = {"feature_id": "F1", "ticket": "t", "layers": []}
    out = [
        event(1, "bare", "run_start", {"spec": spec, "policy_summary": "p"}, TIMES["launch"]),
        event(2, "harness", "run_start", {"spec": spec, "policy_summary": "p"}, TIMES["launch"]),
        event(3, "bare", "primary_verdict", primary("bare", False, 2), TIMES["primary"]),
        event(4, "harness", "primary_verdict", primary("harness", True, 0), "10:05:00"),
    ]
    if full:
        out.append(event(5, "bare", "verdict", verdict(False, 2), TIMES["verdict"]))
        out.append(event(6, "harness", "verdict", verdict(True, 0), "10:07:00"))
    return out


def write_run(runs: Path, *, full: bool) -> None:
    log = runs / AB / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(e.model_dump_json() + "\n" for e in events(full=full)), "utf-8")


def page(tmp_path: Path, *, full: bool) -> dict[str, str]:
    write_run(tmp_path / "runs", full=full)
    app = create_console_app(tmp_path / "runs", exports_dir=tmp_path / "exports")
    response = TestClient(app).get(f"/run/{AB}")
    assert response.status_code == 200
    return screens_of(response.text)


# --- state ---------------------------------------------------------------------------------------


def test_state_after_the_primary_verdict_only() -> None:
    state = ConsoleState.from_events(events(full=False))
    bare = state.arm("bare")
    assert bare.secondary_pending is True
    assert bare.primary_view == {"passed": False, "values": {"r1_new_violations": 2}}
    assert bare.time_to_primary_s == 250.0
    assert bare.time_to_verdict_s is None
    assert bare.claim_supported is None  # no claim in this log
    assert state.arm("harness").primary_view == {"passed": True, "values": {"r1_new_violations": 0}}


def test_state_after_the_full_verdict() -> None:
    state = ConsoleState.from_events(events(full=True))
    bare = state.arm("bare")
    assert bare.secondary_pending is False
    assert bare.primary_view == {"passed": False, "values": {"r1_new_violations": 2}}
    assert (bare.time_to_primary_s, bare.time_to_verdict_s) == (250.0, 390.0)


def test_a_log_without_primary_verdicts_shows_the_full_verdict_as_before() -> None:
    old = [e for e in events(full=True) if e.type != "primary_verdict"]
    bare = ConsoleState.from_events(old).arm("bare")
    assert bare.secondary_pending is False
    assert bare.primary_view == {"passed": False, "values": {"r1_new_violations": 2}}
    assert (bare.time_to_primary_s, bare.time_to_verdict_s) == (None, 390.0)


def test_a_replay_waits_for_the_new_full_verdict() -> None:
    """A replay re-emits the recorded verdict first; the live referee's primary verdict that
    follows starts a new judgement, so secondary checks are running again until its verdict."""
    recorded = events(full=True)
    again = event(7, "bare", "primary_verdict", primary("bare", True, 0), "10:08:00")
    bare = ConsoleState.from_events([*recorded, again]).arm("bare")
    assert bare.secondary_pending is True
    assert bare.primary_view == {"passed": True, "values": {"r1_new_violations": 0}}
    assert bare.time_to_verdict_s is None


def test_tail_line_for_a_primary_verdict() -> None:
    state = ConsoleState.from_events(events(full=False))
    lines = [line.summary for line in state.tail() if line.type == "primary_verdict"]
    assert (
        "primary verdict fail after 12s (House rule 1: Tenant isolation, new violations 2)" in lines
    )


# --- screens 1 and 4 ------------------------------------------------------------------------------


def test_screens_show_the_primary_pill_while_secondary_checks_run(tmp_path: Path) -> None:
    screens = page(tmp_path, full=False)
    for key in ("1", "4"):
        html = screens[key]
        assert "primary verdict ready: FAIL" in html, key
        assert "primary verdict ready: PASS" in html, key
        label = "House rule 1: Tenant isolation, new violations"
        assert f"{label} 2" in html and f"{label} 0" in html, key
        assert html.count("secondary checks running") == 2, key
        assert "launch to primary verdict 04:10" in html, key
        assert "launch to full verdict" not in html, key
        assert "mutants killed 1/2" not in html, key


def test_screens_fill_in_the_secondary_results_with_the_full_verdict(tmp_path: Path) -> None:
    screens = page(tmp_path, full=True)
    for key in ("1", "4"):
        html = screens[key]
        assert "primary verdict ready: FAIL" in html and "primary verdict ready: PASS" in html, key
        assert "secondary checks running" not in html, key
        assert "mutants killed 1/2" in html, key
        assert "launch to primary verdict 04:10" in html, key
        assert "launch to full verdict 06:30" in html, key
        assert "launch to full verdict 07:00" in html, key


def test_screens_before_any_verdict_say_the_referee_is_pending(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    log = runs / AB / "events.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(events(full=False)[0].model_dump_json() + "\n", "utf-8")
    app = create_console_app(runs, exports_dir=tmp_path / "exports")
    screens = screens_of(TestClient(app).get(f"/run/{AB}").text)
    assert "referee pending" in screens["1"] and "referee pending" in screens["4"]
    assert "primary verdict ready" not in screens["1"]
