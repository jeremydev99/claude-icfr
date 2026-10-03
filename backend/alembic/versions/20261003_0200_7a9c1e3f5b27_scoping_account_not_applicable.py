"""스코핑 계정 '해당 없음' — 판정에서 빼는 표시와 사유 (2026-10-03 마스터)

Revision ID: 7a9c1e3f5b27
Revises: 4d6f8a0b2c35
Create Date: 2026-10-03 02:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** `scoping_accounts.not_applicable`(기본 false)·`na_reason`(NULL).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '7a9c1e3f5b27'
down_revision: Union[str, None] = '4d6f8a0b2c35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scoping_accounts', sa.Column('not_applicable', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('scoping_accounts', sa.Column('na_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('scoping_accounts', 'na_reason')
    op.drop_column('scoping_accounts', 'not_applicable')
