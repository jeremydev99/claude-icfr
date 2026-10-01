"""보안 1단계 — 계정 잠금 컬럼 + 로그인 시도 기록 (2026-10-01, 사외 접속 허용 후)

Revision ID: 1c3e5a7b9d20
Revises: f5a6b7c8d9e0
Create Date: 2026-10-01 00:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** `users` 에 컬럼 3개(실패 횟수 0 기본값, 잠금·비밀번호 변경
시각 NULL)와 새 테이블 `login_events`. 기존 사용자의 비밀번호·세션은 그대로다(password_changed_at NULL 이면
토큰 무효화를 하지 않는다).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = '1c3e5a7b9d20'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'login_events',
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(30), nullable=False),
        sa.Column('ip', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(255), nullable=True),
        sa.Column('row_version', sa.Integer(), server_default='1', nullable=False),
    )
    op.create_index('ix_login_events_user_id', 'login_events', ['user_id'])
    op.create_index('ix_login_events_created_at', 'login_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_login_events_created_at', table_name='login_events')
    op.drop_index('ix_login_events_user_id', table_name='login_events')
    op.drop_table('login_events')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
