"""evidence sha256 column

Revision ID: a144dfc162a5
Revises: d13051e6bcf5
Create Date: 2026-06-16 07:49:22.786177+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a144dfc162a5'
down_revision: Union[str, None] = 'd13051e6bcf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evidence_files', sa.Column('sha256', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('evidence_files', 'sha256')
