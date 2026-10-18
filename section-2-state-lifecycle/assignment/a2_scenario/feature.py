"""A multi-step feature: its steps, the files each step writes, and the ticket text.

Step ids are `S1`, `S2`, ... The test stand-in agent commits each step with a subject that
starts with the step id (`S1: Comments table`), so a state layer can read step completion from
the git history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REV_FIELD = "{rev}"
DOWN_FIELD = "{down}"


@dataclass(frozen=True)
class FileSlot:
    """One file a step writes. A migration path contains `{rev}`, the agent's revision id."""

    key: str
    path: str
    template: str

    @property
    def migration(self) -> bool:
        return REV_FIELD in self.path

    def path_for(self, rev: str = "") -> str:
        return self.path.replace(REV_FIELD, rev)

    def pattern(self) -> re.Pattern[str]:
        """Matches this slot's path anywhere in a line (any revision id for a migration)."""
        head, _, tail = self.path.partition(REV_FIELD)
        body = re.escape(head) + (r"([A-Za-z0-9]+)" + re.escape(tail) if self.migration else "")
        return re.compile(r"(?<![\w/.-])" + body + r"(?![\w/-])")

    def render(self, rev: str = "", down: str = "") -> str:
        return self.template.replace(REV_FIELD, rev).replace(DOWN_FIELD, down)


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    description: str
    slots: tuple[FileSlot, ...]

    @property
    def number(self) -> int:
        return int(self.id[1:])

    def line(self) -> str:
        """The step as it appears in the ticket and in `feature_steps`."""
        return f"{self.id} {self.title}: {self.description}"


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    summary: str
    rev_code: str
    base_rev: str
    steps: tuple[Step, ...]

    def step(self, step_id: str) -> Step:
        return next(s for s in self.steps if s.id == step_id)

    def step_lines(self) -> list[str]:
        return [step.line() for step in self.steps]

    def revision(self, step: Step, attempt: int) -> str:
        """Revision id of a step's migration: a fresh attempt picks a fresh id."""
        return f"{self.rev_code}{step.number}a{attempt}"

    def ticket(self) -> str:
        steps = "\n".join(f"- {line}" for line in self.step_lines())
        first = self.steps[0]
        return (
            f"{self.title}\n\n"
            f"{self.summary}\n\n"
            f"Work through the steps in order. Commit each step on its own, with a message that "
            f'starts with the step id (for example "{first.id}: {first.title}").\n\n'
            f"{steps}\n\n"
            f"Alembic migrations live in migrations/versions/. The history must keep exactly one "
            f'head: a new migration\'s down_revision is the current head ("{self.base_rev}" when '
            f"the ticket starts). Run the visible tests before you finish.\n"
        )
