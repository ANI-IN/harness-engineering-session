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
        """The lowest-id live issue of each of the org's projects, deleted in the database.

        Writing the row directly (not through DELETE /issues/{id}) keeps R8 independent of whether
        the build's delete endpoint works; R1-R5 already probe that endpoint.
        """
        from sqlalchemy import text

        org_id = self.ids(org)["org_id"]
        with app.state.session_factory() as session:
            rows = session.execute(
                text(
                    "SELECT MIN(id) FROM issues WHERE org_id = :org AND deleted_at IS NULL "
                    "GROUP BY project_id"
                ),
                {"org": org_id},
            ).all()
            ids = sorted(int(row[0]) for row in rows)
            for issue_id in ids:
                session.execute(
                    text(
                        "UPDATE issues SET deleted_at = CURRENT_TIMESTAMP, title = :title "
                        "WHERE id = :id AND org_id = :org"
                    ),
                    {"title": self.deleted_marker(issue_id), "id": issue_id, "org": org_id},
                )
            session.commit()
        return ids
