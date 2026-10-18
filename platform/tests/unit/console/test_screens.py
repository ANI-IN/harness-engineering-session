"""The five screens render from a fixture run log (and exports for screen 4)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shipharness.console.app import create_console_app, screen_updates
from shipharness.console.screens import ScreenRenderer
from shipharness.events import EventBus
from tests.unit.console.fixture_log import AB_ID, build_fixture_exports, build_fixture_run


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    runs, exports = tmp_path / "runs", tmp_path / "exports"
    build_fixture_run(runs)
    build_fixture_exports(exports)
    return runs, exports


@pytest.fixture
def client(dirs: tuple[Path, Path]) -> TestClient:
    return TestClient(create_console_app(dirs[0], exports_dir=dirs[1], before_class_dir=None))


def screens_of(html: str) -> dict[str, str]:
    """Split the run page into the five screen sections."""
    parts = re.split(r'(?=<section class="screen" id="screen-\d")', html)
    found: dict[str, str] = {}
    for part in parts:
        match = re.match(r'<section class="screen" id="screen-(\d)"', part)
        if match:
            found[match.group(1)] = part
    return found


@pytest.fixture
def page(client: TestClient) -> dict[str, str]:
    response = client.get(f"/run/{AB_ID}")
    assert response.status_code == 200
    return screens_of(response.text)


def test_run_page_has_five_screens_and_key_hints(client: TestClient, page: dict[str, str]) -> None:
    assert sorted(page) == ["1", "2", "3", "4", "5"]
    html = client.get(f"/run/{AB_ID}").text
    for key, name in (
        ("1", "Live"),
        ("2", "Boards"),
        ("3", "Evidence"),
        ("4", "A/B"),
        ("5", "Traces"),
    ):
        assert re.search(rf'data-key="{key}"[^>]*>\s*<kbd>{key}</kbd>\s*{re.escape(name)}', html)
    assert "<kbd>F</kbd>" in html
    assert 'data-run="ab-fixture"' in html


def test_live_console_header_turns_gate_and_claims(page: dict[str, str]) -> None:
    live = page["1"]
    assert "a1b2c3d4e5f6" in live and "f6e5d4c3b2a1" in live
    assert "network none" in live
    assert "CPU 38%" in live and "212 / 1024 MB" in live
    assert "03:03 left" in live
    assert "$0.081 / $0.20" in live
    assert "Session 1 stopped" in live and "Session 2 resumed" in live
    assert "skill loaded: add-endpoint (tier 2)" in live
    assert "House rule 1 probes 112/112" in live or "House rule 1 probes 37/112" in live
    assert re.search(
        r'<span class="sym"[^>]*>✓</span>\s*<span class="label">House rule 1</span>', live
    )
    assert "Agent said" in live and "Referee" in live
    assert "claim not supported" in live and "claim supported" in live


def test_agent_text_is_escaped(page: dict[str, str]) -> None:
    live = page["1"]
    assert "<script>alert" not in live
    assert "&lt;script&gt;alert(" in live


def test_boards_screen(page: dict[str, str]) -> None:
    boards = page["2"]
    assert 'src="/runs/ab-fixture/files/screenshots/bare/board-0001.png' in boards
    assert 'src="/runs/ab-fixture/files/screenshots/harness/board-0001.png' in boards
    assert "other org" in boards and "#21" in boards
    assert "duplicate" in boards and "#7" in boards
    assert "admin@acme.test" in boards
    assert "Two-tab edit conflict" in boards and "lost update" in boards
    assert "only own-org cards" in boards  # harness board has no marks


def test_evidence_screen(page: dict[str, str]) -> None:
    evidence = page["3"].replace("<wbr>", "")  # names carry break points after _ . / -
    for text in (
        "AGENTS.md",
        "map",
        "skill",
        "handbook",
        "redone",
        "out of scope",
        "app/seed.py",
        "migrations/versions/0001_initial.py",
        "pip install requests",
        "mocks the unit under test",
        "m-repo-07",
        "m-issues-02",
        "3 new",  # one row per check: the name, then a short pill
        "House rule 1: Tenant isolation",
        "reviewer",
    ):
        assert text in evidence, text
    assert evidence.count('class="panel') <= 3


def test_report_screen_reads_exports(page: dict[str, str]) -> None:
    report = page["4"]
    for text in ("9/10", "3/10", "8/10", "2/10", "none (bare)", "instructions + state + scope"):
        assert text in report, text
    assert "$0.13 per verified feature" in report
    assert "18/20" in report
    assert "https://smith.langchain.com/o/x/compare/s1" in report
    assert "https://smith.langchain.com/o/x/compare/ab-fixture" in report
    assert "%" not in re.sub(r"<[^>]+>", "", report)  # counts, never percentages
    assert report.count('class="dot pass"') == 22 and report.count('class="dot fail"') == 18


def test_report_screen_without_exports(tmp_path: Path) -> None:
    build_fixture_run(tmp_path / "runs")
    client = TestClient(
        create_console_app(tmp_path / "runs", exports_dir=tmp_path / "none", before_class_dir=None)
    )
    report = screens_of(client.get(f"/run/{AB_ID}").text)["4"]
    assert "No results to compare yet" in report


def test_traces_screen(page: dict[str, str]) -> None:
    traces = page["5"]
    assert "run end completed" in traces
    assert "First wrong turn" in traces
    assert "1.2" in traces and "named by the referee (House rule 1: Tenant isolation)" in traces
    assert "https://smith.langchain.com/o/x/r/bare-agent" in traces


def test_recording_badge_on_every_screen(tmp_path: Path) -> None:
    build_fixture_run(tmp_path / "runs", recorded=True)
    client = TestClient(create_console_app(tmp_path / "runs", exports_dir=tmp_path / "x"))
    screens = screens_of(client.get(f"/run/{AB_ID}").text)
    assert len(screens) == 5
    for key, html in screens.items():
        assert 'class="badge recording"' in html and "RECORDING" in html, key


def test_no_recording_badge_for_a_live_run(page: dict[str, str]) -> None:
    assert all("RECORDING" not in html for html in page.values())


def test_unsandboxed_banner_on_every_screen(tmp_path: Path) -> None:
    log = tmp_path / "runs" / "ab-local" / "events.jsonl"
    with EventBus(log, ab_id="ab-local") as bus:
        bus.publish(
            "sandbox_start",
            {
                "container_id": "local",
                "image": "host",
                "network": "host",
                "cpus": 0.0,
                "memory_mb": 0,
                "pids_limit": 0,
                "user": "host",
                "read_only_root": False,
                "unsandboxed": True,
            },
            run_id="r",
            arm="bare",
        )
    client = TestClient(create_console_app(tmp_path / "runs", exports_dir=tmp_path / "x"))
    screens = screens_of(client.get("/run/ab-local").text)
    assert all(
        "UNSANDBOXED" in html and "results not official" in html for html in screens.values()
    )


def test_screenshot_files_are_served_only_from_the_run_dir(
    client: TestClient, dirs: tuple[Path, Path]
) -> None:
    ok = client.get(f"/runs/{AB_ID}/files/screenshots/bare/board-0001.png")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
    assert client.get(f"/runs/{AB_ID}/files/events.jsonl").status_code == 404
    assert client.get(f"/runs/{AB_ID}/files/../{AB_ID}/events.jsonl").status_code == 404
    assert client.get(f"/runs/{AB_ID}/files/%2e%2e/secret.png").status_code == 404
    assert client.get(f"/runs/{AB_ID}/files/screenshots/missing.png").status_code == 404
    assert client.get("/runs/..%2F/files/x.png").status_code in (400, 404)


def test_unknown_run_page_is_404(client: TestClient) -> None:
    assert client.get("/run/nope").status_code == 404


def test_html_has_a_strict_content_security_policy(client: TestClient) -> None:
    csp = client.get(f"/run/{AB_ID}").headers["content-security-policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_index_links_to_run_pages(client: TestClient) -> None:
    html = client.get("/").text
    assert "shipharness console" in html and f'href="/run/{AB_ID}"' in html


def test_screen_stream_sends_all_screens_with_last_seq_as_id(client: TestClient) -> None:
    response = client.get(f"/screens/{AB_ID}?follow=false")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: screens" in body
    [data_line] = [line for line in body.splitlines() if line.startswith("data: ")]
    payload = json.loads(data_line[len("data: ") :])
    assert sorted(payload["screens"]) == ["1", "2", "3", "4", "5"]
    assert payload["recorded"] is False
    [id_line] = [line for line in body.splitlines() if line.startswith("id: ")]
    assert id_line == f"id: {payload['seq']}"


def test_screen_updates_follow_new_events_and_send_only_changed_screens(
    dirs: tuple[Path, Path],
) -> None:
    runs, exports = dirs
    log = runs / AB_ID / "events.jsonl"
    renderer = ScreenRenderer()

    async def scenario() -> list[dict[str, object]]:
        seen: list[dict[str, object]] = []
        stop = False

        async def consume() -> None:
            async for message in screen_updates(
                log, exports, renderer, AB_ID, poll_s=0.01, should_stop=lambda: stop
            ):
                seen.append(json.loads(message["data"]))

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.15)
        with EventBus(log, ab_id=AB_ID) as bus:
            bus.publish(
                "sandbox_usage",
                {
                    "cpu_pct": 91.0,
                    "mem_mb": 500.0,
                    "mem_limit_mb": 1024.0,
                    "pids": 30,
                    "time_left_s": 12,
                },
                run_id="run-bare",
                arm="bare",
            )
        await asyncio.sleep(0.15)
        stop = True
        await asyncio.wait_for(task, timeout=2)
        return seen

    seen = asyncio.run(scenario())
    assert len(seen) == 2
    first, update = seen
    assert sorted(first["screens"]) == ["1", "2", "3", "4", "5"]  # type: ignore[arg-type]
    assert "CPU 91%" in update["screens"]["1"]  # type: ignore[index]
    assert "4" not in update["screens"]  # type: ignore[operator]
    assert update["seq"] == first["seq"] + 1  # type: ignore[operator]


# --- screen 1 after the run: the full timeline, scrollable ------------------


def _long_run(runs: Path, *, finished: bool) -> None:
    with EventBus(runs / "ab-long" / "events.jsonl", ab_id="ab-long") as bus:

        def emit(type_: str, data: dict) -> None:  # type: ignore[type-arg]
            bus.publish(type_, data, run_id="run-h", arm="harness")

        spec = {"feature_id": "F1", "ticket": "t", "layers": ["instructions"]}
        emit("run_start", {"spec": spec, "policy_summary": "network none"})
        for n in range(1, 13):
            emit(
                "turn",
                {
                    "session_index": 1,
                    "turn": n,
                    "turns_left": 30 - n,
                    "input_tokens": 100,
                    "cached_tokens": 0,
                    "cache_write_tokens": 0,
                    "output_tokens": 10,
                    "reasoning_tokens": 0,
                    "message_excerpt": f"step-{n:02d}",
                },
            )
        for n in range(1, 6):
            emit(
                "harness_decision",
                {"kind": "note", "layer": "instructions", "message": f"decision-{n}x", "paths": []},
            )
        if finished:
            emit(
                "run_end",
                {"status": "completed", "claim": "none", "cost_usd": 0.01, "turns_total": 12,
                 "wall_s": 100.0},
            )  # fmt: skip


def _live_screen(tmp_path: Path, *, finished: bool) -> str:
    _long_run(tmp_path / "runs", finished=finished)
    app = create_console_app(tmp_path / "runs", exports_dir=tmp_path / "exports")
    return screens_of(TestClient(app).get("/run/ab-long").text)["1"]


def test_finished_run_shows_every_turn_and_decision_in_a_scrollable_list(tmp_path: Path) -> None:
    live = _live_screen(tmp_path, finished=True)
    assert all(f"step-{n:02d}" in live for n in range(1, 13))
    assert all(f"decision-{n}x" in live for n in range(1, 6))
    assert 'class="turns scroll-list full"' in live and 'class="decisions scroll-list full"' in live
    assert "All turns" in live and live.count('class="expand-toggle"') >= 2


def test_live_run_shows_the_last_15_turns_and_every_decision(tmp_path: Path) -> None:
    # Owner, 2026-10-18: the lists are at least 15 lines tall, so the live view keeps 15 turns.
    live = _live_screen(tmp_path, finished=False)
    assert all(f"step-{n:02d}" in live for n in range(1, 13))  # 12 turns: all of them
    assert all(f"decision-{n}x" in live for n in range(1, 6))
    assert 'class="turns scroll-list"' in live and "Last turns" in live
