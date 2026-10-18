"""A2 reference solution: ResumableStateLayer.

At every session stop the harness, not the agent, writes the state the next session needs:

1. a step ledger derived from git (step commits, uncommitted product files);
2. the exec plan's Progress section: the ledger plus one line per session;
3. session-handoff.md: the S2 machine summary plus the ledger, with the agent's notes kept;
4. progress.md: its sections (Current feature, Done, In progress, Next, Session log) restored and
   one log entry per session;
5. one harness commit of those files;
6. a resume message with the ledger, the next step, and the migration head;
7. at the end of the phase, the exec plan moved to completed/ with its outcome.

It builds on the S2 layer's helpers in `shipharness.harness.state` (templates, handoff, progress
entry format, safe file writes, sandboxed commits).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from a2_state.ledger import (
    StepStatus,
    derive_ledger,
    is_harness_file,
    next_step,
    parse_commits,
    parse_steps,
    render_ledger,
    replace_section,
    uncommitted_paths,
)
from a2_state.progress_log import normalise_progress
from shipharness.harness.base import BaseLayer, LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.state import handoff, lifecycle, progress
from shipharness.harness.state.commit import commit_paths
from shipharness.harness.state.files import move_file, read_text, write_file
from shipharness.harness.state.templates import (
    ASSETS,
    HANDOFF,
    PROGRESS,
    exec_plan_path,
    fields,
    initial_files,
    render,
)
from shipharness.runner.models import SessionResult

_SHA = re.compile(r"^[0-9a-f]{7,40}$")
GIT_TIMEOUT_S = 30


class ResumableStateLayer(BaseLayer):
    name = "state"

    def __init__(
        self,
        *,
        feature_description: str | None = None,
        feature_steps: list[str] | None = None,
        handoff_test_timeout_s: int = 120,
        clock: Callable[[], datetime] | None = None,
        **_ignored: Any,
    ) -> None:
        self.feature_description = feature_description
        self.feature_steps = feature_steps
        self.handoff_test_timeout_s = handoff_test_timeout_s
        self.clock = clock or (lambda: datetime.now(UTC))
        self.entries: list[str] = []  # progress.md session log, one per session
        self.history: list[str] = []  # exec plan Progress, one line per session
        self.ledger: list[StepStatus] = []
        self.heads = ""
        self.last_tests = ""
        self.last_session = 0
        self._claim_seen: Any = None
        self._plan_moved = False

    # -- evidence -------------------------------------------------------------------------------

    def _steps(self, ctx: LayerContext) -> list:
        return parse_steps(self.feature_steps, ctx.spec.ticket_text)

    def _git(self, ctx: LayerContext, command: str) -> str:
        run = ctx.sandbox.exec(command, GIT_TIMEOUT_S)
        return run.output if run.exit_code == 0 else ""

    def _evidence(self, ctx: LayerContext) -> tuple[list[StepStatus], list[str]]:
        """TODO 1: the ledger from git, and the uncommitted product files."""
        setup = str(ctx.state.get("harness.setup_sha") or "")
        span = f"{setup}..HEAD" if _SHA.match(setup) else "HEAD"
        log = self._git(ctx, f"git log --reverse --no-color --format=%H%x09%s {span}")
        status = self._git(ctx, "git status --porcelain -uall")
        uncommitted = uncommitted_paths(status)
        return derive_ledger(self._steps(ctx), parse_commits(log), uncommitted), uncommitted

    def _changed(self, ctx: LayerContext, result: SessionResult, uncommitted: list[str]) -> list:
        """Product files changed since the session started (committed or not)."""
        names: set[str] = set(uncommitted)
        if _SHA.match(result.start_sha):
            diff = self._git(ctx, f"git diff --name-only --no-color {result.start_sha}")
            names.update(line.strip() for line in diff.splitlines() if line.strip())
        return sorted(n for n in names if not is_harness_file(n))

    # -- hooks ------------------------------------------------------------------------------------

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        files = initial_files(ctx.spec, self.feature_description, self.feature_steps)
        plan = exec_plan_path(ctx.spec.feature_id)
        ledger = render_ledger(derive_ledger(self._steps(ctx), [], []))
        if ledger:
            text = files[plan].decode("utf-8")
            body = ["- [x] Harness initializer step: init.sh, progress.md, handoff, plan.", *ledger]
            files[plan] = replace_section(text, "## Progress", body).encode("utf-8")
        for rel, data in files.items():
            write_file(ctx.workspace, rel, data)
        commit_paths(
            ctx.sandbox, list(files), f"harness: initializer step for {ctx.spec.feature_id}"
        )
        message = "initializer step: " + ", ".join(files)
        return [HarnessDecision(kind="note", layer=self.name, message=message, paths=list(files))]

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return [lifecycle.getting_up_to_speed(ctx.spec)]

    def on_wrapup(self, ctx: LayerContext) -> str | None:
        return (
            "Wrap up this session now. The next session starts with an empty context and "
            "continues from what you leave in the repository:\n"
            '1. Commit finished work with a message that starts with its step id ("S2: ...").\n'
            "2. Update progress.md: Done, In progress, and Next. The harness keeps the Session "
            "log.\n"
            f'3. Write your notes under "{handoff.NOTES}" in session-handoff.md.\n'
            f"4. Record decisions and surprises in {exec_plan_path(ctx.spec.feature_id)} "
            "(Decision Log, Surprises & Discoveries). The harness writes its Progress section "
            "from the git history."
        )

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        ws, feature = ctx.workspace, ctx.spec.feature_id
        self.ledger, uncommitted = self._evidence(ctx)  # TODO 1
        self.heads = handoff.migration_heads(ws)
        changed = self._changed(ctx, result, uncommitted)
        tests, failures = handoff.visible_tests(ctx.sandbox, self.handoff_test_timeout_s)
        self.last_tests, self.last_session = tests, result.index
        stamp = self.clock().strftime("%Y-%m-%dT%H:%MZ")
        self.history.append(
            f"- Session {result.index} ({result.phase}) ended by {result.ended_by} after "
            f"{result.turns} turns at commit {result.end_sha[:7] or 'none'} ({stamp})."
        )
        ledger_lines = render_ledger(self.ledger)

        # TODO 2: the exec plan's Progress section, rebuilt from evidence every time.
        plan = exec_plan_path(feature, "active")
        paths = [HANDOFF, PROGRESS]
        plan_text = read_text(ws, plan)
        if plan_text is not None:
            body = [*ledger_lines, *([""] if ledger_lines else []), *self.history]
            write_file(ws, plan, replace_section(plan_text, "## Progress", body).encode())
            paths.append(plan)

        # TODO 3: the handoff, machine part plus the ledger; the agent's notes stay as written.
        summary = handoff.MachineSummary(
            result=result,
            files_changed=changed,
            tests=tests,
            failures=failures,
            commits=handoff.last_commits(ctx.sandbox),
            todos=handoff.todo_markers(ws, changed),
            heads=self.heads,
        ).render()
        steps_block = self._steps_block(ledger_lines)
        template = (ASSETS / HANDOFF).read_text(encoding="utf-8")
        merged = handoff.merge(read_text(ws, HANDOFF), template, f"{summary}\n{steps_block}")
        write_file(ws, HANDOFF, merged.encode())

        # TODO 4: progress.md, one entry per session, whatever the agent did to the file.
        self.entries.append(progress.session_entry(result, len(changed), tests, self._claim(ctx)))
        values = fields(ctx.spec, self.feature_description, self.feature_steps)
        default = render("progress.md", values).decode("utf-8")
        text = read_text(ws, PROGRESS) or default
        write_file(ws, PROGRESS, normalise_progress(text, default, self.entries).encode())

        # TODO 5: one harness commit for everything written above.
        commit_paths(ctx.sandbox, paths, f"harness: session {result.index} state for {feature}")
        ctx.state["state.handoff_path"] = HANDOFF
        return [
            HarnessDecision(
                kind="session_stop",
                layer=self.name,
                message=f"session {result.index} state written: {', '.join(paths)}",
                paths=paths,
                data={"session_index": result.index, "files_changed": len(changed)},
            )
        ]

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        """TODO 6: what the resumed session needs first: the ledger, the next step, the head."""
        lines = [
            "Start with the Getting up to speed steps before you change code. The harness read "
            f"the git history at the end of session {self.last_session}:",
            *render_ledger(self.ledger),
        ]
        step = next_step(self.ledger)
        if step is not None:
            todo = "finish the files not listed as written, then commit" if step.written else ""
            lines.append(
                f"Next: {step.step.id} {step.step.title}{'; ' + todo if todo else ''}. Commit it "
                f'with a message that starts with "{step.step.id}:".'
            )
        elif not self.ledger:
            lines.append("The ticket has no numbered steps: read the exec plan and the git log.")
        else:
            lines.append("Every step is committed: run the visible tests, then finish.")
        lines.append(f"Migration heads: {self.heads}. A new migration's down_revision is the head.")
        lines.append(
            f"The structured handoff is in {HANDOFF}; the plan is "
            f"{exec_plan_path(ctx.spec.feature_id)}."
        )
        return ["\n".join(lines)]

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        """TODO 7: move the plan when the claim is done and git shows every step committed."""
        last = ctx.state.get("last_claim")
        claimed = isinstance(last, dict) and last.get("claim") == "done"
        if self._plan_moved or not claimed or last.get("phase") != ctx.phase:
            return []
        ledger, _ = self._evidence(ctx)
        if any(s.state != "done" for s in ledger):
            return []
        feature = ctx.spec.feature_id
        active, completed = exec_plan_path(feature, "active"), exec_plan_path(feature, "completed")
        text = read_text(ctx.workspace, active)
        if text is None:
            return []
        lines = render_ledger(ledger)
        text = replace_section(
            text, "## Progress", [*lines, *([""] if lines else []), *self.history]
        )
        commits = ", ".join(f"{s.step.id} {s.commit}" for s in ledger) or "no numbered steps"
        outcome = [
            f"- Finished in session {self.last_session}: the claim is done and every step is "
            f"committed ({commits}).",
            f"- Last visible test run: {self.last_tests or 'not run'}.",
        ]
        text = replace_section(text, "## Outcomes & Retrospective", outcome)
        write_file(ctx.workspace, active, text.encode())
        if not move_file(ctx.workspace, active, completed):
            return []
        self._plan_moved = True
        commit_paths(ctx.sandbox, ["docs/exec-plans"], f"harness: {feature} exec plan completed")
        return [
            HarnessDecision(
                kind="note",
                layer=self.name,
                message=f"exec plan moved to {completed}",
                paths=[active, completed],
            )
        ]

    # -- helpers ----------------------------------------------------------------------------------

    def _steps_block(self, ledger_lines: list[str]) -> str:
        if not ledger_lines:
            return "- Steps: the ticket has no numbered steps."
        indented = "\n".join(f"  {line}" for line in ledger_lines)
        return f"- Steps, from the git history (`S<n>:` commits):\n{indented}"

    def _claim(self, ctx: LayerContext) -> str:
        last = ctx.state.get("last_claim")
        if isinstance(last, dict) and last != self._claim_seen:
            self._claim_seen = dict(last)
            return str(last.get("summary", ""))
        return ""
