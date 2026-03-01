"""add publisher to books

Revision ID: a1b2c3d4e5f6
Revises: 390a85298b3d
Create Date: 2026-02-28 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '390a85298b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('books', sa.Column('publisher', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('books', 'publisher')
