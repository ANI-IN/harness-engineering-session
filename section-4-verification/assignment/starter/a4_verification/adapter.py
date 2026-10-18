"""The app-specific facts R8 needs, on top of the shipharness TenantAppAdapter.

R8 must soft-delete some rows before it can probe, and it must recognise a deleted row in a
response. Both depend on the application, so they go through the adapter, like `audit_count` does
for R5 (`shipharness.checks.adapter`).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from shipharness.checks.adapter import TeamTrackAdapter, TenantAppAdapter


@runtime_checkable
class SoftDeleteAdapter(TenantAppAdapter, Protocol):
    def soft_delete(self, app: Any, org: str) -> list[int]:
        """Soft-delete some of `org`'s issues directly in the database; return their ids.

        The first id returned is the one path probes use.
        """
        ...

    def deleted_marker(self, issue_id: int) -> str:
        """Text that appears in any response that contains the deleted issue `issue_id`."""
        ...


class TeamTrackSoftDeleteAdapter(TeamTrackAdapter):
    """TeamTrack: issues carry `deleted_at`; a soft-deleted issue gets a marker title."""

    def deleted_marker(self, issue_id: int) -> str:
        # The brackets keep "[r8-deleted:1]" from matching inside "[r8-deleted:11]".
        return f"[r8-deleted:{issue_id}]"

    def soft_delete(self, app: Any, org: str) -> list[int]:
        # TODO(A4-1): soft-delete the lowest-id live issue of each of `org`'s projects.
        #   - open a session with `app.state.session_factory()` (see `audit_count` in
        #     shipharness/checks/adapter.py) and use `sqlalchemy.text` queries;
        #   - the org's id is `self.ids(org)["org_id"]`;
        #   - set `deleted_at` to the current time AND set `title` to `self.deleted_marker(id)`,
        #     so a response that contains the row can be recognised by its text;
        #   - commit, and return the ids sorted ascending (the first one is
        #     `self.ids(org)["issue_id"]`, the id other checks use in paths).
        raise NotImplementedError("TODO(A4-1): TeamTrackSoftDeleteAdapter.soft_delete")
