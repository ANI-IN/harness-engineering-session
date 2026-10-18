from __future__ import annotations

from dataclasses import dataclass

WRITER_ROLES = frozenset({"admin", "member"})


@dataclass(frozen=True)
class Actor:
    """The authenticated user making a request. Every service call is scoped to actor.org_id."""

    user_id: int
    org_id: int
    role: str

    @property
    def can_write(self) -> bool:
        return self.role in WRITER_ROLES

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
