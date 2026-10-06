"""감사 로그 대상 이름(target_label) — 추가만 (13.9-98)

Revision ID: b8d0f2a4c6e9
Revises: a7c9e1f3b5d8
Create Date: 2026-10-06 04:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8d0f2a4c6e9'
down_revision: Union[str, None] = 'a7c9e1f3b5d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('target_label', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_logs', 'target_label')
