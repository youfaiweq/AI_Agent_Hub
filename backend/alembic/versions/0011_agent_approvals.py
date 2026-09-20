"""create agent approval requests

Revision ID: 0011_agent_approvals
Revises: 0010_long_term_memories
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_agent_approvals"
down_revision: str | None = "0010_long_term_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("call_id", sa.String(length=120), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id", "call_id", name="uq_agent_approvals_run_call"),
    )
    op.create_index(op.f("ix_agent_approvals_agent_run_id"), "agent_approvals", ["agent_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_approvals_agent_run_id"), table_name="agent_approvals")
    op.drop_table("agent_approvals")
