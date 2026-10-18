"""The step ledger: which ticket steps git shows as done, which is in progress, and its files.

Evidence comes from the repository, never from what the agent wrote about itself: a step is done
when a commit subject starts with its id (`S2: ...`); the first step that is not done is in
progress when the working tree has uncommitted product files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from shipharness.harness.scope.features import ticket_steps

HARNESS_FILES = {
    "progress.md",
    "session-handoff.md",
    "init.sh",
    "feature_list.json",
    "feature_list.schema.json",
}
HARNESS_DIRS = ("docs/exec-plans/",)
_STEP_LINE = re.compile(r"^\s*(S\d+)\b\s*(.*)$")
_STEP_SUBJECT = re.compile(r"^\s*(S\d+)\s*:")

State = Literal["done", "in_progress", "not_started"]


@dataclass(frozen=True)
class TicketStep:
    id: str
    title: str


@dataclass(frozen=True)
class StepStatus:
    step: TicketStep
    state: State
    commit: str = ""
    written: tuple[str, ...] = ()


def parse_steps(feature_steps: list[str] | None, ticket_text: str) -> list[TicketStep]:
    """Steps with an id (`S1 Title: details`), from `feature_steps` or else the ticket's bullets."""
    steps: list[TicketStep] = []
    for line in feature_steps or ticket_steps(ticket_text):
        match = _STEP_LINE.match(line)
        if match and all(s.id != match.group(1) for s in steps):
            title = match.group(2).split(":", 1)[0].strip(" -.") or match.group(1)
            steps.append(TicketStep(match.group(1), title))
    return steps


def parse_commits(log_output: str) -> list[tuple[str, str]]:
    """`git log --format=%H%x09%s` output as (sha, subject) pairs."""
    pairs = []
    for line in log_output.splitlines():
        sha, _, subject = line.partition("\t")
        if re.fullmatch(r"[0-9a-f]{7,40}", sha.strip()):
            pairs.append((sha.strip(), subject))
    return pairs


def is_harness_file(path: str) -> bool:
    return path in HARNESS_FILES or path.startswith(HARNESS_DIRS)


def uncommitted_paths(porcelain: str) -> list[str]:
    """Product files that `git status --porcelain -uall` lists, without the harness's own files."""
    paths = set()
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ", 1)[-1].strip()
        if len(path) > 1 and path[0] == path[-1] == '"':
            path = path[1:-1]
        if path and not is_harness_file(path):
            paths.add(path)
    return sorted(paths)


def derive_ledger(
    steps: list[TicketStep], commits: list[tuple[str, str]], uncommitted: list[str]
) -> list[StepStatus]:
    """`commits` oldest first. The first commit for a step is the one that did it."""
    done: dict[str, str] = {}
    for sha, subject in commits:
        match = _STEP_SUBJECT.match(subject)
        if match and match.group(1) not in done:
            done[match.group(1)] = sha[:7]
    ledger: list[StepStatus] = []
    current_seen = False
    for step in steps:
        if step.id in done:
            ledger.append(StepStatus(step, "done", commit=done[step.id]))
        elif not current_seen and uncommitted:
            ledger.append(StepStatus(step, "in_progress", written=tuple(uncommitted)))
            current_seen = True
        else:
            ledger.append(StepStatus(step, "not_started"))
            current_seen = True
    return ledger


def render_ledger(ledger: list[StepStatus]) -> list[str]:
    lines = []
    for status in ledger:
        head = f"{status.step.id} {status.step.title}"
        if status.state == "done":
            lines.append(f"- [x] {head}: done in commit {status.commit}")
        elif status.state == "in_progress":
            files = ", ".join(status.written)
            lines.append(f"- [ ] {head}: in progress; written but not committed: {files}")
        else:
            lines.append(f"- [ ] {head}: not started")
    return lines


def next_step(ledger: list[StepStatus]) -> StepStatus | None:
    return next((s for s in ledger if s.state != "done"), None)


def replace_section(text: str, heading: str, body: list[str]) -> str:
    """Replace the body of `heading` (up to the next `#` or `##` heading), or append the section."""
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    middle = "\n".join(body)
    if start is None:
        return f"{text.rstrip()}\n\n{heading}\n\n{middle}\n"
    end = next(
        (j for j in range(start + 1, len(lines)) if lines[j].startswith(("# ", "## "))),
        len(lines),
    )
    before = "\n".join(lines[: start + 1])
    after = "\n".join(lines[end:]).rstrip("\n")
    return f"{before}\n\n{middle}\n\n{after}\n" if after.strip() else f"{before}\n\n{middle}\n"
