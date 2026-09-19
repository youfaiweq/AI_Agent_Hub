"""create user-owned agent configurations

Revision ID: 0009_agents
Revises: 0008_agent_runtime
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_agents"
down_revision: str | None = "0008_agent_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_base_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("tool_names", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agents_user_id"), "agents", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_agents_knowledge_base_id"), "agents", ["knowledge_base_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agents_knowledge_base_id"), table_name="agents")
    op.drop_index(op.f("ix_agents_user_id"), table_name="agents")
    op.drop_table("agents")
