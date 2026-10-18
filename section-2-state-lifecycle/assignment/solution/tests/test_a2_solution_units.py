"""Unit tests for the reference solution's ledger and progress-file helpers."""

from __future__ import annotations

import sys
from pathlib import Path

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION))
for name in [m for m in sys.modules if m == "a2_state" or m.startswith("a2_state.")]:
    del sys.modules[name]  # another test may have imported the starter's package

from a2_state.ledger import (  # noqa: E402
    StepStatus,
    TicketStep,
    derive_ledger,
    parse_steps,
    render_ledger,
    replace_section,
    uncommitted_paths,
)
from a2_state.progress_log import normalise_progress  # noqa: E402

STEPS = [TicketStep("S1", "Comments table"), TicketStep("S2", "Service"), TicketStep("S3", "Tests")]
TEMPLATE = (
    "# Progress\n\nIntro.\n\n## Current feature\n\ncomments\n\n## Done\n\n- Nothing yet.\n\n"
    "## In progress\n\n- Nothing yet.\n\n## Next\n\n- Start.\n\n## Session log\n"
)


def test_steps_come_from_feature_steps_or_the_ticket() -> None:
    lines = ["S1 Comments table: a migration", "S2 Service: code", "not a step"]
    assert parse_steps(lines, "") == [
        TicketStep("S1", "Comments table"),
        TicketStep("S2", "Service"),
    ]
    ticket = "Title\n\n- S1 Comments table: a migration\n- other bullet\n- S2 Service: code\n"
    assert [s.id for s in parse_steps(None, ticket)] == ["S1", "S2"]
    assert parse_steps(None, "Add comments.\n\n- a bullet without an id\n") == []


def test_the_ledger_comes_from_step_commits_and_uncommitted_files() -> None:
    commits = [
        ("a" * 40, "S1: Comments table"),
        ("b" * 40, "harness: session 1 handoff"),
        ("c" * 40, "S1: Comments table again"),
    ]
    ledger = derive_ledger(STEPS, commits, ["app/service.py"])
    assert ledger == [
        StepStatus(STEPS[0], "done", commit="aaaaaaa"),
        StepStatus(STEPS[1], "in_progress", written=("app/service.py",)),
        StepStatus(STEPS[2], "not_started"),
    ]
    assert derive_ledger(STEPS, [], [])[0].state == "not_started"


def test_ledger_lines_use_the_stand_in_agents_grammar() -> None:
    ledger = [
        StepStatus(STEPS[0], "done", commit="aaaaaaa"),
        StepStatus(STEPS[1], "in_progress", written=("app/a.py", "app/b.py")),
        StepStatus(STEPS[2], "not_started"),
    ]
    assert render_ledger(ledger) == [
        "- [x] S1 Comments table: done in commit aaaaaaa",
        "- [ ] S2 Service: in progress; written but not committed: app/a.py, app/b.py",
        "- [ ] S3 Tests: not started",
    ]


def test_uncommitted_paths_skip_harness_files() -> None:
    porcelain = (
        " M app/models.py\n?? app/comments/service.py\n M progress.md\n?? session-handoff.md\n"
        " M docs/exec-plans/active/comments.md\nR  old.py -> app/new.py\n"
        '?? "app/odd name.py"\n'
    )
    assert uncommitted_paths(porcelain) == [
        "app/comments/service.py",
        "app/models.py",
        "app/new.py",
        "app/odd name.py",
    ]


def test_replace_section_rewrites_one_body_or_appends_the_section() -> None:
    text = "# Plan\n\n## Progress\n\n- old\n\n## Decision Log\n\n- keep\n"
    out = replace_section(text, "## Progress", ["- new"])
    assert out == "# Plan\n\n## Progress\n\n- new\n\n## Decision Log\n\n- keep\n"
    assert replace_section("# Plan\n", "## Progress", ["- a"]) == "# Plan\n\n## Progress\n\n- a\n"


def test_normalise_progress_restores_a_rewritten_file() -> None:
    clobbered = "# Progress\n\nScratch notes from the agent.\n"
    out = normalise_progress(clobbered, TEMPLATE, ["- Session 1 (build): a", "- Session 2: b"])
    headings = [line for line in out.splitlines() if line.startswith("#")]
    assert headings == [
        "# Progress",
        "## Current feature",
        "## Done",
        "## In progress",
        "## Next",
        "## Session log",
    ]
    assert "Scratch notes from the agent." in out
    assert out.endswith("## Session log\n\n- Session 1 (build): a\n- Session 2: b\n")


def test_normalise_progress_keeps_agent_sections_and_never_duplicates_entries() -> None:
    edited = TEMPLATE.replace("- Nothing yet.\n\n## In", "- S1 table\n\n## In") + (
        "- Session 1 (build): a\n\n## Agent scratch\n\n- idea\n"
    )
    out = normalise_progress(edited, TEMPLATE, ["- Session 1 (build): a", "- Session 2: b"])
    assert out.count("- Session 1 (build): a") == 1
    assert "- S1 table" in out
    assert out.index("## Agent scratch") < out.index("## Session log")
