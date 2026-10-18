"""A2 starter: ResumableStateLayer, a state layer whose history survives three forced stops.

It runs as it is: the initializer step writes init.sh, progress.md, session-handoff.md, and the exec
plan and commits them, and every session gets the Getting up to speed routine. Nothing is written
at a session stop yet, so the next session starts blind and redoes work. `check.py` shows the
result. Fill in TODO 1-7 (README, "Step by step").

Helpers you can build on (read them first):
- shipharness.harness.state.templates: initial_files, render, fields, exec_plan_path, ASSETS
- shipharness.harness.state.handoff: MachineSummary, merge, migration_heads, visible_tests,
  last_commits, todo_markers, NOTES
- shipharness.harness.state.progress: session_entry (the session-log line format)
- shipharness.harness.state.files: read_text, write_file, move_file (never through a link)
- shipharness.harness.state.commit: commit_paths (commits only the paths you name, in the sandbox)
Host code never runs git on the workspace: use ctx.sandbox.exec("git ...", timeout).
"""

from __future__ import annotations

from typing import Any

from a2_state.ledger import StepStatus, parse_steps
from shipharness.harness.base import BaseLayer, LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.state import lifecycle
from shipharness.harness.state.commit import commit_paths
from shipharness.harness.state.files import write_file
from shipharness.harness.state.templates import initial_files
from shipharness.runner.models import SessionResult

GIT_TIMEOUT_S = 30


class ResumableStateLayer(BaseLayer):
    name = "state"

    def __init__(
        self,
        *,
        feature_description: str | None = None,
        feature_steps: list[str] | None = None,
        handoff_test_timeout_s: int = 120,
        **_ignored: Any,
    ) -> None:
        self.feature_description = feature_description
        self.feature_steps = feature_steps
        self.handoff_test_timeout_s = handoff_test_timeout_s
        self.entries: list[str] = []  # progress.md session log, one line per session
        self.history: list[str] = []  # exec plan Progress, one line per session
        self.ledger: list[StepStatus] = []
        self.heads = ""
        self.last_session = 0

    def _steps(self, ctx: LayerContext) -> list:
        return parse_steps(self.feature_steps, ctx.spec.ticket_text)

    def _git(self, ctx: LayerContext, command: str) -> str:
        """Run a git command in the sandbox; "" when it fails."""
        run = ctx.sandbox.exec(command, GIT_TIMEOUT_S)
        return run.output if run.exit_code == 0 else ""

    # -- provided ---------------------------------------------------------------------------------

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        """The initializer step (A2): the files come from the S2 templates, in one commit."""
        files = initial_files(ctx.spec, self.feature_description, self.feature_steps)
        for rel, data in files.items():
            write_file(ctx.workspace, rel, data)
        commit_paths(
            ctx.sandbox, list(files), f"harness: initializer step for {ctx.spec.feature_id}"
        )
        message = "initializer step: " + ", ".join(files)
        return [HarnessDecision(kind="note", layer=self.name, message=message, paths=list(files))]

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        """Getting up to speed (A2). Keep it byte-stable across sessions (cached prefix)."""
        return [lifecycle.getting_up_to_speed(ctx.spec)]

    def on_wrapup(self, ctx: LayerContext) -> str | None:
        return lifecycle.wrapup_text(ctx.spec)

    # -- your work --------------------------------------------------------------------------------

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        """Runs after every session, forced stop or not, before the next session starts.

        TODO 1: build the ledger from evidence: `git log` since ctx.state["harness.setup_sha"]
                (subjects starting with a step id) and `git status --porcelain -uall`
                (uncommitted product files). Use ledger.py (TODO 1a-1c there). Store it in
                self.ledger, and the migration heads (handoff.migration_heads) in self.heads.
        TODO 2: rewrite the exec plan's `## Progress` section (docs/exec-plans/active/<id>.md):
                the ledger lines, then one line per session so far, each with `Session <n>` and
                `ended by <reason>`. Rebuild it from evidence every time: what the agent wrote
                there may be wrong.
        TODO 3: write session-handoff.md: the S2 machine summary (handoff.MachineSummary; it says
                "end of session <n>" and carries "Migration heads: ...") plus the ledger lines,
                merged with handoff.merge so the agent's notes stay as written.
        TODO 4: add one session-log entry (progress.session_entry) to self.entries and write
                progress.md through progress_log.normalise_progress, so the file keeps its
                sections and every entry even if the agent rewrote it.
        TODO 5: commit everything you wrote in one harness commit (commit_paths).
        Return a HarnessDecision(kind="session_stop", ...) describing what you wrote.
        """
        self.last_session = result.index
        return []

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        """TODO 6: the resume text for a resumed session (after the neutral resume sentence).

        Give the ledger lines, the next step (and, if it is in progress, that the listed files
        are already written), and the migration heads as `Migration heads: 1 (<rev>)`.
        """
        return [lifecycle.resume_text("")]

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        """TODO 7: when the last claim (ctx.state["last_claim"]) is "done" and git shows every
        step committed, rebuild the plan's Progress section one last time, replace "Not finished
        yet." under `## Outcomes & Retrospective` with the outcome, move the plan from
        docs/exec-plans/active/ to docs/exec-plans/completed/ (files.move_file), and commit
        `docs/exec-plans`. Do it once."""
        return []
