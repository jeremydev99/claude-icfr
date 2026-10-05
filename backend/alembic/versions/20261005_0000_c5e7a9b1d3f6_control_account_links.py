"""통제 ↔ 계정 연결 + 제안 결재 확장 (ADR-0040)

Revision ID: c5e7a9b1d3f6
Revises: b3d5f7a9c1e4
Create Date: 2026-10-05 00:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 `control_account_links`,
`proposals.requested_by_id`·`proposal_items` 통제 칸 4개(전부 NULL).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'c5e7a9b1d3f6'
down_revision: Union[str, None] = 'b3d5f7a9c1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'control_account_links',
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
        sa.Column('control_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('control_code', sa.String(50), nullable=True),
        sa.Column('control_name', sa.String(300), nullable=True),
        sa.Column('fs_account_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('note_key', sa.String(200), nullable=True),
        sa.Column('account_key', sa.String(220), nullable=False),
        sa.Column('account_name', sa.String(200), nullable=False),
        sa.Column('statement_type', sa.String(10), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('remove_state', sa.String(20), nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('match_kind', sa.String(20), nullable=True),
        sa.Column('match_token', sa.String(200), nullable=True),
        sa.Column('proposal_id', PG_UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['fs_account_id', 'tenant_id'], ['fs_accounts.id', 'fs_accounts.tenant_id'],
                                name='fk_control_account_links_fs_account_tenant'),
    )
    op.create_index('ix_control_account_links_control_id', 'control_account_links', ['control_id'])
    op.create_index('ix_control_account_links_fs_account_id', 'control_account_links', ['fs_account_id'])
    op.create_index('ix_control_account_links_proposal_id', 'control_account_links', ['proposal_id'])
    op.create_index('uq_control_account_links_key', 'control_account_links',
                    ['tenant_id', 'control_id', 'account_key'], unique=True,
                    postgresql_where=sa.text('NOT is_deleted'))
    op.add_column('proposals', sa.Column('requested_by_id', PG_UUID(as_uuid=True), nullable=True))
    op.add_column('proposal_items', sa.Column('control_id', PG_UUID(as_uuid=True), nullable=True))
    op.add_column('proposal_items', sa.Column('control_code', sa.String(50), nullable=True))
    op.add_column('proposal_items', sa.Column('control_name', sa.String(300), nullable=True))
    op.add_column('proposal_items', sa.Column('link_id', PG_UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    for c in ('link_id', 'control_name', 'control_code', 'control_id'):
        op.drop_column('proposal_items', c)
    op.drop_column('proposals', 'requested_by_id')
    op.drop_index('uq_control_account_links_key', table_name='control_account_links')
    op.drop_index('ix_control_account_links_proposal_id', table_name='control_account_links')
    op.drop_index('ix_control_account_links_fs_account_id', table_name='control_account_links')
    op.drop_index('ix_control_account_links_control_id', table_name='control_account_links')
    op.drop_table('control_account_links')
