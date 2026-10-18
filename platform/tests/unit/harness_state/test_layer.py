"""StateLayer (S2): initializer, Getting up to speed, wrap-up, handoff, resume, progress log."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shipharness.harness.state.commit import commit_command
from shipharness.harness.state.layer import StateLayer
from shipharness.runner.models import SessionResult
from shipharness.sandbox import ExecResult, FakeSandbox

from ..fakes import fake_openai_key
from ..harness_scope.helpers import call, make_ctx

INIT_FILES = [
    "init.sh",
    "progress.md",
    "session-handoff.md",
    "docs/exec-plans/active/F3.md",
]
PYTEST_OUT = (
    "F...\nFAILED tests/visible/test_a.py::test_x - assert 1 == 2\n1 failed, 3 passed in 0.4s\n"
)


def scripted(**extra: ExecResult) -> FakeSandbox:
    script = {
        "python -m pytest": ExecResult(exit_code=1, output=PYTEST_OUT, duration_ms=5),
        "git log": ExecResult(
            exit_code=0,
            output="d" * 7 + " feat: idempotency table\n" + "c" * 7 + " init\n",
            duration_ms=1,
        ),
        **extra,
    }
    return FakeSandbox(script)


def session(index: int = 1, ended_by: str = "turn_budget", phase: str = "build") -> SessionResult:
    return SessionResult(
        index=index,
        phase=phase,  # type: ignore[arg-type]
        turns=6,
        ended_by=ended_by,  # type: ignore[arg-type]
        start_sha="a" * 40,
        end_sha="b" * 40,
    )


def prepared(tmp_path: Path, sandbox=None, **spec):  # type: ignore[no-untyped-def]
    ctx = make_ctx(tmp_path / "ws", sandbox or scripted(), **spec)
    (ctx.workspace / "app").mkdir()
    (ctx.workspace / "app" / "api.py").write_text("x = 1\n", encoding="utf-8")
    layer = StateLayer()
    layer.prepare_workspace(ctx)
    return ctx, layer


def text(ctx, rel: str) -> str:  # type: ignore[no-untyped-def]
    return (ctx.workspace / rel).read_text(encoding="utf-8")


# --- initializer step ----------------------------------------------------------------------------


def test_initializer_writes_the_state_files_and_commits_them(tmp_path: Path) -> None:
    sandbox = scripted()
    ctx, _layer = prepared(tmp_path, sandbox)
    for rel in INIT_FILES:
        assert (ctx.workspace / rel).is_file(), rel
    assert sandbox.commands[0] == commit_command(INIT_FILES, "harness: initializer step for F3")


def test_initializer_output_is_deterministic(tmp_path: Path) -> None:
    first, _ = prepared(tmp_path / "one")
    second, _ = prepared(tmp_path / "two")
    for rel in INIT_FILES:
        assert (first.workspace / rel).read_bytes() == (second.workspace / rel).read_bytes()


def test_init_sh_sets_up_and_runs_a_basic_test(tmp_path: Path) -> None:
    ctx, _ = prepared(tmp_path)
    data = (ctx.workspace / "init.sh").read_bytes()
    assert b"\r\n" not in data
    script = data.decode("utf-8")
    assert script.startswith("#!/usr/bin/env bash\n")
    assert "walkthrough" not in script
    assert "alembic upgrade head" in script
    assert "pytest tests/visible" in script
    assert "uvicorn app.main:create_app --factory" in script
    assert "Feature 3: Safe retries for issue creation" in script


def test_progress_md_has_the_contract_sections_in_order(tmp_path: Path) -> None:
    ctx, _ = prepared(tmp_path)
    body = text(ctx, "progress.md")
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == [
        "# Progress",
        "## Current feature",
        "## Done",
        "## In progress",
        "## Next",
        "## Session log",
    ]
    assert "Feature 3: Safe retries for issue creation. Idempotency keys on create-issue" in body
    assert "{{" not in body


def test_exec_plan_has_the_a7_sections(tmp_path: Path) -> None:
    ctx, _ = prepared(tmp_path)
    body = text(ctx, "docs/exec-plans/active/F3.md")
    headings = [line[3:] for line in body.splitlines() if line.startswith("## ")]
    assert headings == [
        "Purpose",
        "Progress",
        "Surprises & Discoveries",
        "Decision Log",
        "Outcomes & Retrospective",
        "Validation",
    ]
    assert "- POST /projects/{id}/issues with Idempotency-Key twice" in body
    assert "{{" not in body


def test_handoff_template_has_both_sections(tmp_path: Path) -> None:
    ctx, _ = prepared(tmp_path)
    body = text(ctx, "session-handoff.md")
    assert "## Machine summary" in body and "## Notes from the agent" in body


def test_unknown_constructor_kwargs_are_ignored() -> None:
    StateLayer(feature_steps=["a"], gate_checks=["r1"])


# --- prefix, wrap-up, resume ---------------------------------------------------------------------


def test_getting_up_to_speed_block_is_stable(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    first = layer.context_prefix(ctx)
    ctx.phase, ctx.session_index, ctx.turn = "test", 3, 9
    assert layer.context_prefix(ctx) == first
    block = "\n".join(first)
    assert block.startswith("## Getting up to speed")
    for needle in ("pwd", "progress.md", "git log", "feature_list.json", "init.sh"):
        assert needle in block, needle
    assert "run_visible_tests" in block
    assert block.index("pwd") < block.index("progress.md") < block.index("init.sh")


def test_prefix_without_scope_does_not_mention_the_feature_list(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, layers=frozenset({"state"}))
    assert "feature_list.json" not in "\n".join(layer.context_prefix(ctx))


def test_wrapup_asks_for_progress_exec_plan_handoff_and_commit(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    wrapup = layer.on_wrapup(ctx)
    assert wrapup is not None
    for needle in (
        "progress.md",
        "docs/exec-plans/active/F3.md",
        "session-handoff.md",
        "Notes from the agent",
        "commit",
    ):
        assert needle in wrapup, needle


# --- session stop -----------------------------------------------------------------------------


def stop_session(ctx, layer, index: int = 1, **kwargs):  # type: ignore[no-untyped-def]
    ctx.session_index = index
    layer.before_tool(ctx, call("run", command="true", timeout_s=None))
    (ctx.workspace / "app" / "api.py").write_text("x = 2  # TODO handle conflicts\n", "utf-8")
    (ctx.workspace / "app" / "idem.py").write_text("y = 1\n", encoding="utf-8")
    return layer.on_session_end(ctx, session(index, **kwargs))


def test_session_stop_writes_the_machine_summary(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    decisions = stop_session(ctx, layer)
    body = text(ctx, "session-handoff.md")
    summary = body.split("## Machine summary", 1)[1].split("## Notes from the agent", 1)[0]
    assert "session 1" in summary and "turn_budget" in summary
    assert "app/api.py" in summary and "app/idem.py" in summary
    assert "passed=3 failed=1 errors=0" in summary
    assert "FAILED tests/visible/test_a.py::test_x" in summary
    assert "feat: idempotency table" in summary
    assert "app/api.py:1: x = 2  # TODO handle conflicts" in summary
    assert "Migration heads: no migrations found" in summary
    assert ctx.state["state.handoff_path"] == "session-handoff.md"
    assert [d.kind for d in decisions] == ["session_stop"]
    assert decisions[0].paths == ["session-handoff.md", "progress.md"]


def test_session_stop_keeps_the_agent_notes(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    handoff = ctx.workspace / "session-handoff.md"
    handoff.write_text(
        text(ctx, "session-handoff.md").replace("- What is left:", "- What is left: migration"),
        encoding="utf-8",
    )
    stop_session(ctx, layer)
    assert "- What is left: migration" in text(ctx, "session-handoff.md")
    assert text(ctx, "session-handoff.md").count("## Notes from the agent") == 1


def test_session_stop_appends_one_progress_log_entry_per_session(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    progress = ctx.workspace / "progress.md"
    progress.write_text(
        text(ctx, "progress.md").replace("## Done\n\n- Nothing yet.", "## Done\n\n- Table added."),
        encoding="utf-8",
    )
    ctx.state["last_claim"] = {"phase": "build", "claim": "not_done", "summary": "half way"}
    stop_session(ctx, layer, 1)
    stop_session(ctx, layer, 2, ended_by="claim_done")
    body = text(ctx, "progress.md")
    assert "- Table added." in body
    log = body.split("## Session log", 1)[1].strip().splitlines()
    assert len(log) == 2
    assert log[0].startswith(
        "- Session 1 (build): start aaaaaaa, end bbbbbbb, ended by turn_budget"
    )
    assert log[1].startswith("- Session 2 (build): start aaaaaaa, end bbbbbbb, ended by claim_done")
    assert "half way" in log[0]


def test_session_log_heading_is_restored_if_the_agent_removed_it(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    (ctx.workspace / "progress.md").write_text("# Progress\n\nnotes\n", encoding="utf-8")
    stop_session(ctx, layer)
    body = text(ctx, "progress.md")
    assert body.count("## Session log") == 1
    assert body.split("## Session log", 1)[1].strip().startswith("- Session 1 (build)")


def test_session_stop_commits_only_the_harness_files(tmp_path: Path) -> None:
    sandbox = scripted()
    ctx, layer = prepared(tmp_path, sandbox)
    stop_session(ctx, layer)
    assert sandbox.commands[-1] == commit_command(
        ["session-handoff.md", "progress.md"], "harness: session 1 handoff for F3"
    )


def test_agent_controlled_text_is_masked_and_capped(tmp_path: Path) -> None:
    key = fake_openai_key()
    noisy = ExecResult(exit_code=0, output=f"abc1234 leak {key} " + "z" * 500 + "\n", duration_ms=1)
    ctx, layer = prepared(tmp_path, scripted(**{"git log": noisy}))
    stop_session(ctx, layer)
    body = text(ctx, "session-handoff.md")
    assert key not in body
    assert "z" * 300 not in body


def test_migration_heads_are_counted_from_the_files(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    versions = ctx.workspace / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_initial.py").write_text(
        'revision = "0001_initial"\ndown_revision = None\n', encoding="utf-8"
    )
    (versions / "0002_a.py").write_text(
        'revision = "0002_a"\ndown_revision = "0001_initial"\n', encoding="utf-8"
    )
    (versions / "0002_b.py").write_text(
        'revision: str = "0002_b"\ndown_revision: str | None = "0001_initial"\n', encoding="utf-8"
    )
    stop_session(ctx, layer)
    assert "Migration heads: 2 (0002_a, 0002_b)" in text(ctx, "session-handoff.md")


def test_session_without_tool_calls_lists_no_changed_files(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    ctx.session_index = 1
    layer.on_session_end(ctx, session(1))
    assert "Files changed in this session (0)" in text(ctx, "session-handoff.md")


def test_resume_text_carries_the_handoff(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    stop_session(ctx, layer, 1)
    ctx.session_index = 2
    blocks = layer.on_session_start(ctx)
    resume = "\n".join(blocks)
    assert "Getting up to speed" in resume
    assert "session-handoff.md" in resume
    assert "app/idem.py" in resume  # the machine summary travels with the resume text


def test_handoff_link_is_replaced_not_followed(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("symlink creation needs privileges on Windows")
    ctx, layer = prepared(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("keep\n", encoding="utf-8")
    (ctx.workspace / "session-handoff.md").unlink()
    (ctx.workspace / "session-handoff.md").symlink_to(outside)
    stop_session(ctx, layer)
    assert outside.read_text(encoding="utf-8") == "keep\n"
    assert not (ctx.workspace / "session-handoff.md").is_symlink()


# --- exec plan completion ----------------------------------------------------------------------


def test_exec_plan_moves_to_completed_when_passes_is_set(tmp_path: Path) -> None:
    sandbox = scripted()
    ctx, layer = prepared(tmp_path, sandbox)
    ctx.state["scope.passes_set"] = True
    decisions = layer.on_phase_end(ctx)
    assert not (ctx.workspace / "docs/exec-plans/active/F3.md").exists()
    assert (ctx.workspace / "docs/exec-plans/completed/F3.md").is_file()
    assert [d.kind for d in decisions] == ["note"]
    assert sandbox.commands[-1] == commit_command(
        ["docs/exec-plans"], "harness: F3 exec plan completed"
    )
    assert layer.on_phase_end(ctx) == []  # moved once


def test_exec_plan_stays_active_without_passes(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    assert layer.on_phase_end(ctx) == []
    assert (ctx.workspace / "docs/exec-plans/active/F3.md").is_file()


# --- overhead cuts (M6 pilot: the full visible suite ran twice at every session start) -----------


def test_init_sh_basic_test_is_one_end_to_end_file_not_the_full_suite() -> None:
    from shipharness.harness.state.templates import ASSETS

    text = (ASSETS / "init.sh").read_text(encoding="utf-8")
    assert "python -m pytest tests/visible/test_issues.py -x" in text
    assert "python -m pytest tests/visible -x" not in text
    assert "basic end-to-end test" in text


def test_getting_up_to_speed_reuses_the_handoff_test_status(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    block = "\n".join(layer.context_prefix(ctx))
    assert "Run the visible tests with run_visible_tests. If something" not in block
    assert '"Visible tests" line' in block and "session-handoff.md" in block
    assert "first session" in block


# --- turn cost (harness change, harness arm only; approved after pilot run 2) -------------
# In run 2 the harness arm re-read every instruction document and the product code in every
# session and kept progress.md and the exec plan up to date mid-session; in F2 it wrote no product
# code in 50 build turns, and in F4 almost no tests in the 12-turn test phase.


def test_getting_up_to_speed_reads_the_agent_notes_before_any_document(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    block = "\n".join(layer.context_prefix(ctx))
    assert '"Notes from the agent"' in block
    assert "only for a detail the notes do not cover" in block
    assert block.index("session-handoff.md") < block.index("Notes from the agent")


def test_bookkeeping_waits_for_the_wrap_up(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    block = "\n".join(layer.context_prefix(ctx))
    assert "only when the harness asks you to wrap up" in block
    assert "End each session with a git commit and a progress update" not in block


def test_wrapup_asks_for_the_rules_that_matter_for_this_ticket(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    wrapup = layer.on_wrapup(ctx) or ""
    assert "house rules and file locations" in wrapup
    assert "does not need to read them again" in wrapup


def test_machine_summary_lists_the_documents_read_so_far(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    ctx.state["instructions.files_read"] = ["AGENTS.md", "docs/SECURITY.md"]
    stop_session(ctx, layer)
    body = text(ctx, "session-handoff.md")
    assert "- Harness documents read so far: AGENTS.md, docs/SECURITY.md" in body


def test_test_phase_resume_puts_the_feature_tests_first(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path)
    stop_session(ctx, layer, 1)
    ctx.session_index, ctx.phase = 2, "build"
    assert "tests for the feature first" not in "\n".join(layer.on_session_start(ctx))
    ctx.phase = "test"
    assert "tests for the feature first" in "\n".join(layer.on_session_start(ctx))
