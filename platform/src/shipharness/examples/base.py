"""Building blocks for constructed examples: a scenario, scripted tool calls that cost nothing, and
the reference change of a feature, file by file.

A constructed example is not a measurement. Its steps are written in advance, so it shows what a
layer does when an agent makes the mistake the layer exists to catch, the same way every time.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from shipharness.config.prices import REPO_ROOT
from shipharness.cost import Usage
from shipharness.layout import APP_DIR
from shipharness.runner.model import Step, tool_step

REFERENCE_DIR = REPO_ROOT / APP_DIR / "reference"
NO_USAGE = Usage(input_tokens=0, output_tokens=0)  # scripted steps call no model: $0


@dataclass(frozen=True)
class Scenario:
    """One constructed example: section N's layer stack on its canonical task (feature FN)."""

    section: str  # demo-1..demo-4: the layer stack (ab.demo.SECTION_STACKS)
    feature: str  # the section's canonical task
    title: str  # what the scripted agent does, in one line
    demonstrates: str  # what the class sees the layer do, in one sentence
    steps: Callable[[], list[Step]]  # a fresh script for every run
    session_budget: tuple[int, ...] | None = None  # overrides the task's build-session budget


def act(name: str, **arguments: object) -> Step:
    """One scripted tool call (no model, no tokens)."""
    return tool_step(name, usage=NO_USAGE, **arguments)


def read(path: str) -> Step:
    return act("read_file", path=path)


def patch(text: str) -> Step:
    return act("apply_patch", patch=text)


def run(command: str) -> Step:
    return act("run", command=command)


def commit(message: str) -> Step:
    return run(f"git add -A && git commit -q -m {shlex.quote(message)}")


def finish(claim: str, summary: str) -> Step:
    return act("finish", claim=claim, summary=summary)


def reference_patch(feature: str, paths: Sequence[str]) -> str:
    """The sections of the course's reference change for `feature` that touch `paths`, in that
    order. The change is platform/teamtrack/reference/<f>/<f>.patch, a git diff against the
    checkpoint."""
    name = feature.lower()
    text = (REFERENCE_DIR / name / f"{name}.patch").read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    for chunk in re.split(r"(?m)^(?=diff --git )", text):
        if chunk.startswith("diff --git "):
            first = chunk.split("\n", 1)[0]
            sections[first.split(" b/", 1)[1]] = chunk
    missing = [p for p in paths if p not in sections]
    if missing:
        raise KeyError(f"not in the {feature} reference change: {', '.join(missing)}")
    return "".join(sections[p] for p in paths)
