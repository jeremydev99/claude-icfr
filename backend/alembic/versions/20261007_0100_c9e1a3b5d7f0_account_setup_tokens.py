"""직원 계정 설정 링크 — 추가만 (ADR-0041, 13.9-99)

Revision ID: c9e1a3b5d7f0
Revises: b8d0f2a4c6e9
Create Date: 2026-10-07 01:00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 `account_setup_tokens`, `users` 에 기본값 false 인
`invite_pending`·`must_change_password` 두 열(기존 계정은 모두 false = 지금과 같다).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9e1a3b5d7f0'
down_revision: Union[str, None] = 'b8d0f2a4c6e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'account_setup_tokens',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('purpose', sa.String(length=10), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('issued_by_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.Column('row_version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_account_setup_tokens_token_hash', 'account_setup_tokens', ['token_hash'], unique=True)
    op.create_index('ix_account_setup_tokens_user_id', 'account_setup_tokens', ['user_id'], unique=False)
    op.add_column('users', sa.Column('invite_pending', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'invite_pending')
    op.drop_index('ix_account_setup_tokens_user_id', table_name='account_setup_tokens')
    op.drop_index('ix_account_setup_tokens_token_hash', table_name='account_setup_tokens')
    op.drop_table('account_setup_tokens')
