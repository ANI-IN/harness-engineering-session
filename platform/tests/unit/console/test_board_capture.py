"""Board capture logic that does not need a browser: overlay marks and the output protocol."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from shipharness.console.board_capture import (
    MARKER,
    build_parser,
    capture_line,
    compute_overlays,
)
from tests.unit.console.fixture_log import tiny_png


def card(index: int, issue_id: int | str, org: str, title: str) -> dict[str, object]:
    return {"index": index, "issue_id": issue_id, "org": org, "title": title}


def test_own_org_cards_get_no_marks() -> None:
    cards = [card(0, 1, "acme", "Login bug"), card(1, 2, "acme", "Slow board")]
    assert compute_overlays(cards, "acme") == []


def test_cards_from_another_org_are_marked() -> None:
    cards = [card(0, 1, "acme", "Login bug"), card(1, 21, "globex", "Globex secret")]
    assert compute_overlays(cards, "acme") == [
        {"index": 1, "issue_id": 21, "mark": "other_org", "label": "OTHER ORG: globex"}
    ]


def test_duplicate_titles_and_repeated_ids_are_marked_on_the_later_card() -> None:
    cards = [
        card(0, 5, "acme", "Add labels"),
        card(1, 6, "acme", "  add   LABELS "),  # same title after normalising: duplicate create
        card(2, 5, "acme", "Add labels"),  # same id rendered twice
    ]
    overlays = compute_overlays(cards, "acme")
    assert [(o["index"], o["issue_id"], o["mark"]) for o in overlays] == [
        (1, 6, "duplicate"),
        (2, 5, "duplicate"),
    ]
    assert overlays[0]["label"] == "DUPLICATE of #5"


def test_a_card_can_carry_both_marks() -> None:
    cards = [card(0, 21, "globex", "X"), card(1, 22, "globex", "x")]
    marks = [(o["index"], o["mark"]) for o in compute_overlays(cards, "acme")]
    assert marks == [(0, "other_org"), (1, "other_org"), (1, "duplicate")]


def test_non_numeric_ids_are_kept_as_text_and_missing_org_is_other() -> None:
    overlays = compute_overlays([card(0, "abc", "", "t")], "acme")
    assert overlays == [
        {"index": 0, "issue_id": "abc", "mark": "other_org", "label": "OTHER ORG: unknown"}
    ]


def test_capture_line_is_one_marker_line_with_base64_png() -> None:
    png = tiny_png()
    line = capture_line("board", "admin@acme.test", [{"issue_id": 21, "mark": "other_org"}], png)
    assert line.startswith(MARKER) and "\n" not in line
    payload = json.loads(line[len(MARKER) :])
    assert payload["view"] == "board" and payload["as_user"] == "admin@acme.test"
    assert payload["overlays"] == [{"issue_id": 21, "mark": "other_org"}]
    assert base64.b64decode(payload["png_b64"]) == png


@pytest.mark.parametrize(
    "argv",
    [
        ["once", "--base-url", "http://127.0.0.1:8000"],
        ["once", "--view", "conflict"],
        ["loop", "--interval", "5", "--out-dir", "/tmp/shots"],
        ["serve", "--app-dir", "/work", "--db", "/tmp/preview.db"],
        ["wait", "--timeout", "30"],
    ],
)
def test_cli_parses(argv: list[str]) -> None:
    args = build_parser().parse_args(argv)
    assert args.command == argv[0]


def test_cli_defaults_view_the_board_as_acme() -> None:
    args = build_parser().parse_args(["once"])
    assert (args.user, args.org, args.view) == ("admin@acme.test", "acme", "board")
    assert args.base_url == "http://127.0.0.1:8000"
    loop = build_parser().parse_args(["loop"])
    assert loop.interval == 5.0


def test_preview_server_reloads_when_the_arm_changes_its_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The preview starts before the agent works; without reload it would show the checkpoint."""
    import uvicorn

    from shipharness.console import board_capture

    seen: dict[str, object] = {}
    monkeypatch.setattr(board_capture, "prepare_database", lambda app_dir, db: "sqlite:///x.db")
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: seen.update(kw))
    board_capture.serve(tmp_path / "work", tmp_path / "db.sqlite", 8000)
    assert seen["reload"] is True
    assert seen["reload_dirs"] == [str(tmp_path / "work" / "app")]
