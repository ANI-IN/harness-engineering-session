"""Session lifecycle text and the session stop.

Getting up to speed follows A2 (F-a-58 to F-a-62); the session end follows A2's "End the session
by writing a git commit and progress update" (F-a-63); the stop and resume are A3's context reset
with a structured handoff (F-a-65).
"""

from __future__ import annotations

from pathlib import Path

from shipharness.harness.base import LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.state import handoff, progress
from shipharness.harness.state.commit import commit_paths
from shipharness.harness.state.files import read_text, write_file
from shipharness.harness.state.templates import ASSETS, HANDOFF, PROGRESS, exec_plan_path
from shipharness.runner.models import AgentRunSpec, SessionResult


def getting_up_to_speed(spec: AgentRunSpec) -> str:
    steps = [
        "Run `pwd` to see the directory you are working in. You can only edit files in this "
        "directory.",
        "Read progress.md and the git log (`git log --oneline -20`) to see what was recently "
        "worked on.",
        f"Read session-handoff.md (the structured handoff from the last session) and the exec "
        f"plan {exec_plan_path(spec.feature_id)}.",
        'Read the "Notes from the agent" in session-handoff.md before any other document: '
        "earlier sessions wrote down the house rules and files that matter for this ticket. Open a "
        "document from the AGENTS.md map only for a detail the notes do not cover (in the first "
        "session, only the documents for the parts you will change).",
    ]
    if "scope" in spec.layers:
        steps.append("Read feature_list.json and work on the feature listed there, and only it.")
    steps += [
        "Run `bash init.sh` to set up the database and run a basic end-to-end test.",
        'Read the "Visible tests" line in session-handoff.md: the harness ran the full visible '
        "suite when the last session ended. If it lists failures, fix them before you start new "
        "work. In the first session there is no such line yet: run the visible tests once with "
        "run_visible_tests.",
    ]
    numbered = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1))
    return (
        "## Getting up to speed\n"
        "This ticket can take more than one session, and every session starts with an empty "
        "context. What earlier sessions did is in the repository and its git history. At the "
        "start of every session, before you change code:\n"
        f"{numbered}\n"
        "Work on one step at a time and commit with a descriptive message when a step works. "
        "Spend the session on the ticket: update progress.md, the exec plan, and the handoff only "
        "when the harness asks you to wrap up."
    )


def wrapup_text(spec: AgentRunSpec) -> str:
    return (
        "Wrap up this session now. The next session starts with an empty context and continues "
        "from what you leave in the repository:\n"
        "1. Update progress.md: Done, In progress, and Next.\n"
        f"2. Update the exec plan {exec_plan_path(spec.feature_id)}: Progress (with timestamps) "
        "and Decision Log.\n"
        f'3. Write your notes under "{handoff.NOTES}" in session-handoff.md: what you were '
        "doing, what is left, what to watch out for, and the house rules and file locations from "
        "the documents you read that matter for this ticket, so the next session does not need to "
        "read them again. The harness writes the machine summary itself.\n"
        "4. Commit your work to git with a descriptive message (git add, then git commit)."
    )


def machine_summary(
    ctx: LayerContext, result: SessionResult, files_changed: list[str], timeout_s: int
) -> tuple[str, str]:
    """The rendered machine summary and the visible-test status line."""
    tests, failures = handoff.visible_tests(
        ctx.sandbox, timeout_s, state=ctx.state, workspace=ctx.workspace
    )
    summary = handoff.MachineSummary(
        result=result,
        files_changed=files_changed,
        tests=tests,
        failures=failures,
        commits=handoff.last_commits(ctx.sandbox),
        todos=handoff.todo_markers(ctx.workspace, files_changed),
        heads=handoff.migration_heads(ctx.workspace),
        docs_read=list(ctx.state.get("instructions.files_read", [])),
    )
    return summary.render(), tests


TEST_PHASE_FIRST = (
    "This session is in the test phase: write the tests for the feature first, as new files under "
    "tests/visible/, and run them; open other documents only if a test needs them."
)


# [walkthrough:S2:stop_resume] start
def session_stop(
    ctx: LayerContext, result: SessionResult, files_changed: list[str], claim: str, timeout_s: int
) -> tuple[list[HarnessDecision], str]:
    """Write the machine part of the handoff and the progress log entry, then commit them."""
    ws: Path = ctx.workspace
    summary, tests = machine_summary(ctx, result, files_changed, timeout_s)
    template = (ASSETS / HANDOFF).read_text(encoding="utf-8")
    write_file(ws, HANDOFF, handoff.merge(read_text(ws, HANDOFF), template, summary).encode())
    log = read_text(ws, PROGRESS) or (ASSETS / PROGRESS).read_text(encoding="utf-8")
    entry = progress.session_entry(result, len(files_changed), tests, claim)
    write_file(ws, PROGRESS, progress.append_session_entry(log, entry).encode())
    commit_paths(
        ctx.sandbox,
        [HANDOFF, PROGRESS],
        f"harness: session {result.index} handoff for {ctx.spec.feature_id}",
    )
    ctx.state["state.handoff_path"] = HANDOFF
    stop = HarnessDecision(
        kind="session_stop",
        layer="state",
        message=f"session {result.index} handoff written to {HANDOFF}",
        paths=[HANDOFF, PROGRESS],
        data={"session_index": result.index, "files_changed": len(files_changed)},
    )
    return [stop], summary


def resume_text(summary: str, phase: str = "build") -> str:
    """Extra resume text for the harness arm (the neutral resume sentence comes first)."""
    text = (
        "Start with the Getting up to speed steps before you change code. The structured "
        "handoff from the last session is in session-handoff.md."
    )
    if phase == "test":
        text = f"{text} {TEST_PHASE_FIRST}"
    return f"{text} Its machine summary:\n\n{summary[:3000]}" if summary else text


# [walkthrough:S2:stop_resume] end
