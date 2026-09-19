"""add document processing metadata

Revision ID: 0005_document_processing
Revises: 0004_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_document_processing"
down_revision: str | None = "0004_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("documents", "chunk_count", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "chunk_count")
