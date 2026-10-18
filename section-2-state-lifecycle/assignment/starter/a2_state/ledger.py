"""The step ledger: which ticket steps git shows as done, which is in progress, and its files.

Evidence comes from the repository, never from what the agent wrote about itself. The ticket's
steps have ids (`S1`, `S2`, ...); the test stand-in agent commits each step with a subject that
starts with its id (`S2: Comment service`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HARNESS_FILES = {
    "progress.md",
    "session-handoff.md",
    "init.sh",
    "feature_list.json",
    "feature_list.schema.json",
}
HARNESS_DIRS = ("docs/exec-plans/",)

State = Literal["done", "in_progress", "not_started"]


@dataclass(frozen=True)
class TicketStep:
    id: str  # "S1"
    title: str  # "Comments table"


@dataclass(frozen=True)
class StepStatus:
    step: TicketStep
    state: State
    commit: str = ""  # 7-character hash of the commit that did the step, when done
    written: tuple[str, ...] = ()  # uncommitted product files, when in progress


def parse_steps(feature_steps: list[str] | None, ticket_text: str) -> list[TicketStep]:
    """Steps with an id, from `feature_steps` (lines like "S1 Comments table: details") or, when
    that is empty, from the ticket's bullet lines
    (`shipharness.harness.scope.features.ticket_steps`).

    TODO 1a: return the steps in order; the title is the text between the id and the first ":".
    Lines without an `S<n>` id are not steps.
    """
    return []


def parse_commits(log_output: str) -> list[tuple[str, str]]:
    """`git log --format=%H%x09%s` output as (sha, subject) pairs. Provided."""
    pairs = []
    for line in log_output.splitlines():
        sha, _, subject = line.partition("\t")
        if sha.strip():
            pairs.append((sha.strip(), subject))
    return pairs


def is_harness_file(path: str) -> bool:
    return path in HARNESS_FILES or path.startswith(HARNESS_DIRS)


def uncommitted_paths(porcelain: str) -> list[str]:
    """Product files listed by `git status --porcelain -uall`, without the harness's own files.
    Provided (renames show as `old -> new`; quoted paths lose their quotes)."""
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
    """One StepStatus per step, from the evidence. `commits` is oldest first.

    TODO 1b:
    - a step is "done" when a commit subject starts with its id and a colon; keep the first such
      commit's 7-character hash (a second one would be redone work);
    - the first step that is not done is "in_progress" when there are uncommitted product files,
      with those files in `written`;
    - every other step is "not_started".
    """
    return [StepStatus(step, "not_started") for step in steps]


def render_ledger(ledger: list[StepStatus]) -> list[str]:
    """Markdown lines the next session reads. TODO 1c.

    The test stand-in agent's reading rules (SPEC.md, "Inputs") decide what works:
    a line with `[x]` and the step id marks the step done; a line with the step id and the word
    "written" names files already on disk. For example:
        - [x] S1 Comments table: done in commit 615f2d2
        - [ ] S2 Comment service: in progress; written but not committed: app/comments/service.py
        - [ ] S3 Index and tests: not started
    """
    return []


def next_step(ledger: list[StepStatus]) -> StepStatus | None:
    return next((s for s in ledger if s.state != "done"), None)


def replace_section(text: str, heading: str, body: list[str]) -> str:
    """Replace the body of `heading` (up to the next `#` or `##` heading), or append the section.
    Provided."""
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
