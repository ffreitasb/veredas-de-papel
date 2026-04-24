"""add_mercado_column_to_taxa_cdb

Revision ID: c7e9f3a5b2d1
Revises: 4360d097bff0
Create Date: 2026-04-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e9f3a5b2d1"
down_revision: str | None = "4360d097bff0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("taxas_cdb", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mercado", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("taxas_cdb", schema=None) as batch_op:
        batch_op.drop_column("mercado")
