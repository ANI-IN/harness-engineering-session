"""labels and issue labels

Revision ID: 0004_labels
Revises: 0003_watchers
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_labels"
down_revision = "0003_watchers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("orgs.id"), nullable=False, index=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_labels_org_name"),
    )
    op.create_table(
        "issue_labels",
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), primary_key=True),
        sa.Column(
            "label_id", sa.Integer(), sa.ForeignKey("labels.id"), primary_key=True, index=True
        ),
    )


def downgrade() -> None:
    op.drop_table("issue_labels")
    op.drop_table("labels")
