"""The test stand-in agent (literal_agent.py, not a model): what it treats as known, and which
tool call it makes next."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))

from a2_scenario.literal_agent import (  # noqa: E402
    LiteralAgent,
    decide,
    read_knowledge,
)
from a2_scenario.scenarios import COMMENTS  # noqa: E402

from shipharness.runner.prompts import NEUTRAL_RESUME, wrapup_message  # noqa: E402

PLAN = "docs/exec-plans/active/comments.md"


def msg(role: str, text: str) -> dict[str, Any]:
    return {"role": role, "content": [{"type": "input_text", "text": text}]}


def base(resume: str | None = None) -> list[dict[str, Any]]:
    items = [msg("developer", "prefix mentioning progress.md"), msg("user", COMMENTS.ticket())]
    if resume is not None:
        items.append(msg("user", f"{NEUTRAL_RESUME}\n\n{resume}"))
    return items


def add_call(items: list[dict[str, Any]], name: str, output: str, **arguments: Any) -> None:
    call_id = f"call_{len(items)}"
    items.append(
        {
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(arguments),
        }
    )
    items.append({"type": "function_call_output", "call_id": call_id, "output": output})


def oriented(files: dict[str, str] | None = None, resume: str | None = None) -> list[dict]:
    """A session whose three orientation reads are done, with the given file texts."""
    files = files or {}
    items = base(resume)
    for path in ("progress.md", "session-handoff.md", PLAN):
        add_call(items, "read_file", files.get(path, f"file not found: {path}"), path=path)
    return items


def args(action: Any) -> dict[str, Any]:
    return action.arguments


# -- knowledge -----------------------------------------------------------------------------


def test_a_checked_box_with_the_step_id_marks_the_step_done() -> None:
    k = read_knowledge(COMMENTS, ["- [x] S1 Comments table: done in commit abc1234"])
    assert k.done == {"S1"}


def test_ticket_style_lines_and_commit_lines_are_not_knowledge() -> None:
    texts = [
        "- S1 Comments table: one migration that creates the comments table",
        "  - abc1234 S1: Comments table",
        "- [x] Harness initializer step: init.sh, progress.md",
    ]
    k = read_knowledge(COMMENTS, texts)
    assert k.done == set() and k.written == {}


def test_a_written_line_names_the_files_already_on_disk() -> None:
    line = (
        "- [ ] S1 Comments table: in progress; written but not committed: "
        "migrations/versions/c1a1_comments.py"
    )
    k = read_knowledge(COMMENTS, [line])
    assert k.written == {"S1": {"migration": "migrations/versions/c1a1_comments.py"}}
    assert k.done == set()


def test_the_migration_head_comes_from_a_heads_line() -> None:
    k = read_knowledge(COMMENTS, ["- Migration heads: 1 (c1a1)"])
    assert k.head == "c1a1"
    assert read_knowledge(COMMENTS, ["- Migration heads: 2 (c1a1, c1a2)"]).head is None


# -- next action ---------------------------------------------------------------------------


def test_a_session_starts_with_three_orientation_reads() -> None:
    items = base()
    seen = []
    for _ in range(3):
        action = decide(COMMENTS, items, attempt=1)
        assert action.name == "read_file"
        seen.append(args(action)["path"])
        add_call(items, "read_file", "x", path=args(action)["path"])
    assert seen == ["progress.md", "session-handoff.md", PLAN]


def test_with_no_knowledge_the_agent_writes_s1_from_the_ticket_base() -> None:
    action = decide(COMMENTS, oriented(), attempt=1)
    assert action.label == "write S1 migrations/versions/c1a1_comments.py"
    assert "down_revision" in action.content and '"0001"' in action.content


def test_a_fresh_attempt_redoes_unknown_work_with_new_text() -> None:
    first = decide(COMMENTS, oriented(), attempt=1)
    second = decide(COMMENTS, oriented(), attempt=2)
    assert first.label != second.label  # a new revision id
    assert first.content != second.content


def test_after_writing_a_steps_files_the_agent_commits_it() -> None:
    items = oriented()
    for _ in range(2):
        action = decide(COMMENTS, items, attempt=1)
        add_call(items, "run", "exit=0\n", command=args(action)["command"])
    action = decide(COMMENTS, items, attempt=1)
    assert action.label == "commit S1"
    assert '-m "S1: Comments table"' in args(action)["command"]


def test_known_done_steps_and_written_files_are_skipped() -> None:
    plan = (
        "## Progress\n- [x] S1 Comments table: done in commit abc1234\n"
        "- [ ] S2 Comment service: in progress; written but not committed: "
        "app/comments/service.py\n"
    )
    action = decide(COMMENTS, oriented({PLAN: plan}), attempt=2)
    assert action.label == "write S2 app/comments/validation.py"


def test_the_index_migration_uses_the_head_from_the_handoff() -> None:
    plan = "- [x] S1 a: done\n- [x] S2 b: done\n"
    handoff = "- Migration heads: 1 (c1a1)\n"
    files = {PLAN: plan, "session-handoff.md": handoff}
    action = decide(COMMENTS, oriented(files), attempt=3)
    assert action.label == "write S3 migrations/versions/c3a3_comment_index.py"
    assert 'down_revision = "c1a1"' in action.content


def test_knowledge_can_come_from_the_resume_text_alone() -> None:
    resume = "- [x] S1 Comments table: done\n- [x] S2 Comment service: done"
    action = decide(COMMENTS, oriented(resume=resume), attempt=3)
    assert action.label.startswith("write S3 ")


def test_when_every_step_is_done_it_runs_the_tests_then_finishes() -> None:
    plan = "- [x] S1 a\n- [x] S2 b\n- [x] S3 c\n"
    items = oriented({PLAN: plan})
    action = decide(COMMENTS, items, attempt=4)
    assert action.name == "run_visible_tests"
    add_call(items, "run_visible_tests", "passed=4 failed=0 errors=0", selector=None)
    action = decide(COMMENTS, items, attempt=4)
    assert action.name == "finish" and args(action)["claim"] == "done"


def test_a_behaviour_runs_once_after_the_wrapup_message() -> None:
    items = oriented()
    assert decide(COMMENTS, items, attempt=1, behaviour="tick").label.startswith("write ")
    items.append(msg("user", wrapup_message(2, "harness wrap-up text")))
    action = decide(COMMENTS, items, attempt=1, behaviour="tick")
    assert action.label == "tick S2"
    add_call(items, "run", "exit=0\n", command=args(action)["command"])
    assert decide(COMMENTS, items, attempt=1, behaviour="tick").label.startswith("write ")


# -- commands run --------------------------------------------------------------------------


def run_in(ws: Path, command: str) -> None:
    subprocess.run(command, shell=True, cwd=ws, check=True, capture_output=True)


def test_write_commands_create_valid_python_with_a_draft_marker(tmp_path: Path) -> None:
    action = decide(COMMENTS, oriented(), attempt=1)
    run_in(tmp_path, args(action)["command"])
    text = (tmp_path / "migrations/versions/c1a1_comments.py").read_text(encoding="utf-8")
    assert "# draft 1" in text and 'revision = "c1a1"' in text
    compile(text, "migration", "exec")


def test_behaviour_commands_edit_the_state_files(tmp_path: Path) -> None:
    (tmp_path / "docs/exec-plans/active").mkdir(parents=True)
    (tmp_path / PLAN).write_text("# plan\n\n## Progress\n\n- [ ] S1 a\n", encoding="utf-8")
    (tmp_path / "session-handoff.md").write_text(
        "# Session handoff\n\n## Notes from the agent\n\n- What I was doing:\n", encoding="utf-8"
    )
    (tmp_path / "progress.md").write_text("# Progress\n\n## Session log\n", encoding="utf-8")
    items = oriented()
    items.append(msg("user", wrapup_message(2, None)))
    for kind in ("tick", "note", "clobber"):
        run_in(tmp_path, args(decide(COMMENTS, items, attempt=1, behaviour=kind))["command"])
    assert "- [x] S2 Comment service: done" in (tmp_path / PLAN).read_text(encoding="utf-8")
    notes = (tmp_path / "session-handoff.md").read_text(encoding="utf-8")
    assert "literal-agent-note-1" in notes
    progress = (tmp_path / "progress.md").read_text(encoding="utf-8")
    assert "## Session log" not in progress and "Scratch notes" in progress


# -- the model client ----------------------------------------------------------------------


def test_the_client_counts_sessions_and_records_actions() -> None:
    agent = LiteralAgent(COMMENTS)
    kwargs = dict(model="m", effort="low", max_output_tokens=100, service_tier="auto")
    first = agent.respond(base(), [], **kwargs)
    assert first.output_items[0]["type"] == "function_call"
    assert first.output_items[0]["name"] == "read_file"
    agent.respond(base("resume"), [], **kwargs)
    assert agent.attempt == 2
    assert [(a.session, a.label) for a in agent.actions] == [
        (1, "read progress.md"),
        (2, "read progress.md"),
    ]
