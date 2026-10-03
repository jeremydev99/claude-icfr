"""외부 사용자 초대·접근 범위·재확인 + 사용자 MFA (ADR-0039)

Revision ID: b3d5f7a9c1e4
Revises: 7a9c1e3f5b27
Create Date: 2026-10-04 00:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 3개(`invitations`·`external_profiles`·`access_reviews`)와
`users` MFA 칸 4개(전부 NULL). 기존 사용자의 로그인은 그대로다(MFA 미등록 = 기존과 같음, 내부 의무는 유예일부터).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'b3d5f7a9c1e4'
down_revision: Union[str, None] = '7a9c1e3f5b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_cols() -> list:
    return [
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', PG_UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(255), nullable=True),
        sa.Column('row_version', sa.Integer(), server_default='1', nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        'invitations', *_audit_cols(),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('user_type', sa.String(20), nullable=False),
        sa.Column('organization', sa.String(200), nullable=False),
        sa.Column('modules', sa.JSON(), nullable=True),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending_approval'),
        sa.Column('requested_by_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('approved_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('token_hash', sa.String(64), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_user_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confidentiality_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_reason', sa.Text(), nullable=True),
    )
    op.create_index('ix_invitations_email', 'invitations', ['email'])
    op.create_index('ix_invitations_token_hash', 'invitations', ['token_hash'])
    op.create_table(
        'external_profiles', *_audit_cols(),
        sa.Column('user_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('user_type', sa.String(20), nullable=False),
        sa.Column('organization', sa.String(200), nullable=False),
        sa.Column('modules', sa.JSON(), nullable=True),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('invitation_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_reviewed_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('closed_reason', sa.Text(), nullable=True),
    )
    op.create_index('ix_external_profiles_user_id', 'external_profiles', ['user_id'])
    op.create_table(
        'access_reviews', *_audit_cols(),
        sa.Column('reviewed_by_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('snapshot', sa.JSON(), nullable=False),
    )
    op.add_column('users', sa.Column('mfa_secret_enc', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('mfa_pending_enc', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('mfa_recovery', sa.JSON(), nullable=True))


def downgrade() -> None:
    for c in ('mfa_recovery', 'mfa_enabled_at', 'mfa_pending_enc', 'mfa_secret_enc'):
        op.drop_column('users', c)
    op.drop_table('access_reviews')
    op.drop_index('ix_external_profiles_user_id', table_name='external_profiles')
    op.drop_table('external_profiles')
    op.drop_index('ix_invitations_token_hash', table_name='invitations')
    op.drop_index('ix_invitations_email', table_name='invitations')
    op.drop_table('invitations')
