"""감사 로그 — 상태 변경 요청·다운로드 기록(추가만)

Revision ID: e5a7c9d1f3b6
Revises: d7f9b1c3e5a8
Create Date: 2026-10-06 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 `audit_logs` 1개.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'e5a7c9d1f3b6'
down_revision: Union[str, None] = 'd7f9b1c3e5a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('tenant_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_name', sa.String(100), nullable=True),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('route', sa.String(300), nullable=False),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('module', sa.String(40), nullable=False),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('target_id', sa.String(64), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('ip', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(300), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
    )
    for col in ('occurred_at', 'tenant_id', 'user_id', 'module', 'action', 'success'):
        op.create_index(f'ix_audit_logs_{col}', 'audit_logs', [col])


def downgrade() -> None:
    for col in ('occurred_at', 'tenant_id', 'user_id', 'module', 'action', 'success'):
        op.drop_index(f'ix_audit_logs_{col}', table_name='audit_logs')
    op.drop_table('audit_logs')
