"""The test stand-in agent (literal_agent.py): a deterministic program, not a model.

It plays the agent in the offline A2 scenarios and is used for grading only, so scores repeat.

It implements the runner's model-client protocol, so the real loop (`shipharness.runner.loop`) runs
it with the real tools, sessions, wrap-up messages, and forced stops. Each call is decided from the
current session's transcript only, so every session starts with an empty context, as a resumed
model session does. Its rules (SPEC.md, "Inputs"):

1. Every session starts with three reads: progress.md, session-handoff.md, and the exec plan
   `docs/exec-plans/active/<feature>.md` (one turn each).
2. What it knows comes only from those reads and from the resume message, line by line:
   - a line with `[x]` and a step id (`S2`) marks that step done;
   - otherwise a line with a step id and the word "written" names files of that step that are
     already on disk (it will not write them again);
   - `Migration heads: 1 (<rev>)` gives the current head for a new migration's down_revision.
   It never infers progress from commit lines, file listings, or the ticket.
3. It works through the steps in order: one turn per file it writes, one turn for the step commit
   (subject `S<n>: <title>`). When every step is done it runs the visible tests, then finishes.
4. It ignores wrap-up messages and keeps working, unless the scenario gives it a behaviour for
   that session ("note", "clobber", "tick"), which it performs once after the wrap-up message.

Work it does not know about is done again, as a fresh attempt: a new migration file with a new
revision id, and files rewritten with a different draft marker on every line (a fresh model attempt
words the same code differently).
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Any

from a2_scenario.feature import Feature, FileSlot, Step
from shipharness.cost import Usage
from shipharness.harness.state.templates import HANDOFF, PROGRESS, exec_plan_path
from shipharness.runner.model import ModelResponse
from shipharness.runner.prompts import NEUTRAL_RESUME, NEUTRAL_WRAPUP

MARKER = "#a2:"
AGENT_GIT = "git -c user.name=literal-agent -c user.email=agent@a2.invalid"
PRODUCT_DIRS = "app migrations tests"
_CHECKED = re.compile(r"\[[xX]\]")
_HEADS = re.compile(r"Migration heads: 1 \(([A-Za-z0-9_]+)\)")
_STEP_ID = re.compile(r"\bS\d+\b")
_MARK = re.compile(r"#a2:(\S+)\s*$")


@dataclass
class Knowledge:
    done: set[str] = field(default_factory=set)
    written: dict[str, dict[str, str]] = field(default_factory=dict)  # step -> slot key -> path
    head: str | None = None


@dataclass(frozen=True)
class Action:
    name: str
    arguments: dict[str, Any]
    label: str
    content: str = ""  # the file text, for a write


@dataclass(frozen=True)
class ActionRecord:
    session: int
    turn: int
    label: str


def orientation_paths(feature: Feature) -> list[str]:
    return [PROGRESS, HANDOFF, exec_plan_path(feature.id)]


def read_knowledge(feature: Feature, texts: list[str]) -> Knowledge:
    known = Knowledge()
    ids = {step.id for step in feature.steps}
    for text in texts:
        for line in text.splitlines():
            if match := _HEADS.search(line):
                known.head = match.group(1)
            steps = [s for s in dict.fromkeys(_STEP_ID.findall(line)) if s in ids]
            if not steps:
                continue
            if _CHECKED.search(line):
                known.done.update(steps)
            elif "written" in line.lower():
                for step_id in steps:
                    for slot in feature.step(step_id).slots:
                        if found := slot.pattern().search(line):
                            known.written.setdefault(step_id, {})[slot.key] = found.group(0)
    return known


# -- transcript --------------------------------------------------------------------------------


def _text(item: dict[str, Any]) -> str:
    parts = item.get("content") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


@dataclass
class _Session:
    """What the current session's transcript shows: messages, reads, and the agent's own work."""

    resume: list[str] = field(default_factory=list)
    reads: dict[str, str] = field(default_factory=dict)  # path -> output
    wrapup: bool = False
    written: dict[str, dict[str, str]] = field(default_factory=dict)
    migrations: list[str] = field(default_factory=list)  # revision ids written, in order
    committed: set[str] = field(default_factory=set)
    tests_run: bool = False
    behaviour_done: bool = False
    calls: int = 0


def _session(feature: Feature, items: list[dict[str, Any]]) -> _Session:
    view = _Session()
    outputs = {
        i.get("call_id"): str(i.get("output", ""))
        for i in items
        if i.get("type") == "function_call_output"
    }
    for item in items:
        if item.get("type") == "function_call":
            view.calls += 1
            _record_call(feature, view, item, outputs.get(item.get("call_id"), ""))
        elif item.get("role") == "user":
            text = _text(item)
            if text.startswith(NEUTRAL_RESUME):
                view.resume.append(text)
            elif text.startswith(NEUTRAL_WRAPUP):
                view.wrapup = True
    return view


def _record_call(feature: Feature, view: _Session, item: dict[str, Any], output: str) -> None:
    name = item.get("name")
    arguments = json.loads(item.get("arguments") or "{}")
    if name == "read_file":
        view.reads[str(arguments.get("path"))] = output
    elif name == "run_visible_tests":
        view.tests_run = True
    elif name == "run":
        match = _MARK.search(str(arguments.get("command", "")))
        if not match:
            return
        kind, *rest = match.group(1).split(":")
        ok = output.startswith("exit=0")
        if kind == "behaviour":
            view.behaviour_done = True
        elif kind == "commit" and ok:
            view.committed.add(rest[0])
        elif kind == "write" and ok:
            step_id, slot_key, path = rest
            view.written.setdefault(step_id, {})[slot_key] = path
            slot = next(s for s in feature.step(step_id).slots if s.key == slot_key)
            if slot.migration and (found := slot.pattern().search(path)):
                view.migrations.append(found.group(1))


# -- commands ----------------------------------------------------------------------------------


def python_command(script: str, marker: str) -> str:
    """A one-line shell command that runs `script` (base64, so no quoting problems)."""
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return f"python -c \"import base64;exec(base64.b64decode('{encoded}'))\" {MARKER}{marker}"


def with_draft_marker(text: str, attempt: int) -> str:
    """Mark every line with the attempt, except lines that open a bracket: the S2 continuity check
    reads `create_table(` and the table name on the next line as one pattern."""
    return "".join(
        f"{line}  # draft {attempt}\n" if line.strip() and line[-1:] not in "([{" else f"{line}\n"
        for line in text.splitlines()
    )


def _write(feature: Feature, step: Step, slot: FileSlot, attempt: int, down: str) -> Action:
    rev = feature.revision(step, attempt) if slot.migration else ""
    path = slot.path_for(rev)
    content = with_draft_marker(slot.render(rev, down), attempt)
    script = (
        "import pathlib\n"
        f"p = pathlib.Path({path!r})\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        f"p.write_text({content!r}, encoding='utf-8', newline='\\n')\n"
    )
    command = python_command(script, f"write:{step.id}:{slot.key}:{path}")
    return Action(
        "run", {"command": command, "timeout_s": None}, f"write {step.id} {path}", content
    )


def _commit(step: Step) -> Action:
    command = (
        f"git add -A -- {PRODUCT_DIRS} && {AGENT_GIT} commit -q --allow-empty --no-verify "
        f'-m "{step.id}: {step.title}" {MARKER}commit:{step.id}'
    )
    return Action("run", {"command": command, "timeout_s": None}, f"commit {step.id}")


def _behaviour(feature: Feature, kind: str, current: Step | None, attempt: int) -> Action:
    steps = list(feature.steps)
    step = current or steps[-1]
    if kind == "tick":
        target = steps[min(steps.index(step) + 1, len(steps) - 1)]
        line = f"- [x] {target.id} {target.title}: done"
        script = (
            "import pathlib\n"
            f"p = pathlib.Path({exec_plan_path(feature.id)!r})\n"
            "if p.is_file():\n"
            "    lines = p.read_text(encoding='utf-8').splitlines()\n"
            "    at = [i for i, t in enumerate(lines) if t.strip() == '## Progress']\n"
            "    if at:\n"
            f"        lines[at[0] + 1:at[0] + 1] = ['', {line!r}]\n"
            "    else:\n"
            f"        lines += ['', '## Progress', '', {line!r}]\n"
            "    p.write_text('\\n'.join(lines) + '\\n', encoding='utf-8', newline='\\n')\n"
        )
        label = f"tick {target.id}"
    elif kind == "note":
        note = (
            f"- What I was doing: session {attempt} worked on {step.id} {step.title} "
            f"(literal-agent-note-{attempt})"
        )
        script = (
            "import pathlib\n"
            f"p = pathlib.Path({HANDOFF!r})\n"
            "text = p.read_text(encoding='utf-8') if p.is_file() else '# Session handoff\\n'\n"
            "lines = text.splitlines()\n"
            "at = [i for i, t in enumerate(lines) if t.startswith('- What I was doing:')]\n"
            "if at:\n"
            f"    lines[at[0]] = {note!r}\n"
            "else:\n"
            "    if '## Notes from the agent' not in text:\n"
            "        lines += ['', '## Notes from the agent', '']\n"
            f"    lines.append({note!r})\n"
            "p.write_text('\\n'.join(lines) + '\\n', encoding='utf-8', newline='\\n')\n"
        )
        label = "note in session-handoff.md"
    elif kind == "clobber":
        text = (
            f"# Progress\n\nScratch notes from the agent, session {attempt}: working on "
            f"{step.id} {step.title}.\n"
        )
        script = (
            "import pathlib\n"
            f"pathlib.Path({PROGRESS!r}).write_text({text!r}, encoding='utf-8', newline='\\n')\n"
        )
        label = "rewrite progress.md"
    else:
        raise ValueError(f"unknown behaviour: {kind}")
    command = python_command(script, f"behaviour:{kind}")
    return Action("run", {"command": command, "timeout_s": None}, label)


# -- the decision --------------------------------------------------------------------------------


def decide(
    feature: Feature, items: list[dict[str, Any]], attempt: int, behaviour: str | None = None
) -> Action:
    """The next tool call, from this session's transcript only."""
    view = _session(feature, items)
    for path in orientation_paths(feature):
        if path not in view.reads:
            args = {"path": path, "start_line": None, "max_lines": None}
            return Action("read_file", args, f"read {path}")
    known = read_knowledge(feature, [*view.resume, *view.reads.values()])
    pending = [s for s in feature.steps if s.id not in known.done | view.committed]
    current = pending[0] if pending else None
    if behaviour and view.wrapup and not view.behaviour_done:
        return _behaviour(feature, behaviour, current, attempt)
    if current is not None:
        have = {**known.written.get(current.id, {}), **view.written.get(current.id, {})}
        for slot in current.slots:
            if slot.key not in have:
                down = (view.migrations or [known.head or feature.base_rev])[-1]
                return _write(feature, current, slot, attempt, down)
        return _commit(current)
    if not view.tests_run:
        return Action("run_visible_tests", {"selector": None}, "run visible tests")
    summary = "Every step is committed and the visible tests were run."
    return Action("finish", {"claim": "done", "summary": summary}, "finish done")


class LiteralAgent:
    """Test stand-in agent for `run_agent` (it implements the model-client protocol; it is not a
    model). The only state it keeps across sessions is the attempt number (a fresh session words
    new code differently); it carries no knowledge between sessions."""

    def __init__(self, feature: Feature, behaviours: dict[int, str] | None = None) -> None:
        self.feature = feature
        self.behaviours = dict(behaviours or {})
        self.attempt = 0
        self.actions: list[ActionRecord] = []

    def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        effort: str,
        max_output_tokens: int,
        service_tier: str,
    ) -> ModelResponse:
        turn = sum(1 for i in input_items if i.get("type") == "function_call") + 1
        if turn == 1:
            self.attempt += 1
        action = decide(self.feature, input_items, self.attempt, self.behaviours.get(self.attempt))
        self.actions.append(ActionRecord(self.attempt, turn, action.label))
        item = {
            "type": "function_call",
            "id": f"fc_{self.attempt}_{turn}",
            "call_id": f"call_{self.attempt}_{turn}",
            "name": action.name,
            "arguments": json.dumps(action.arguments),
        }
        return ModelResponse(
            output_items=[item], usage=Usage(input_tokens=100, output_tokens=20), text=""
        )
