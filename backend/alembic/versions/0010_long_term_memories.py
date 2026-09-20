"""create explicit long-term memories

Revision ID: 0010_long_term_memories
Revises: 0009_agents
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_long_term_memories"
down_revision: str | None = "0009_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "long_term_memories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_long_term_memories_user_id"), "long_term_memories", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_long_term_memories_memory_type"),
        "long_term_memories",
        ["memory_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_long_term_memories_memory_type"), table_name="long_term_memories")
    op.drop_index(op.f("ix_long_term_memories_user_id"), table_name="long_term_memories")
    op.drop_table("long_term_memories")
