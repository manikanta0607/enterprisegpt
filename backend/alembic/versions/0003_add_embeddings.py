"""enable pgvector and add embedding column to chunks

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-03 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSIONS = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "chunks",
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
    )

    # IVFFlat index for fast approximate cosine-similarity search. `lists`
    # is a reasonable default for small-to-medium corpora; it should be
    # tuned (roughly sqrt(row_count)) as an organization's document volume grows.
    op.execute(
        "CREATE INDEX ix_chunks_embedding_cosine ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_cosine")
    op.drop_column("chunks", "embedding")
