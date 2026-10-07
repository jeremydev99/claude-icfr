"""검토·승인 거버넌스 2-1 — 공통 결재 상태 `approval_states` (ADR-0038 §3)

Revision ID: c1e3a5b7d9f2
Revises: d1f3b5c7e9a2
Create Date: 2026-10-07 03:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 1개. 스코핑은 자기 칸(`scopings.review_*`)을 그대로 쓴다.
재무제표(2-2)부터 이 표를 쓴다. 행이 없는 확정 재무제표 = 2단계 이전 방식 확정(그대로 인정, Q3).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'c1e3a5b7d9f2'
down_revision: Union[str, None] = 'd1f3b5c7e9a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'approval_states',
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
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('review_requested_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('review_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_path', sa.String(20), nullable=True),
        sa.Column('reviewed_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('legacy_confirmed', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index('ix_approval_states_entity_id', 'approval_states', ['entity_id'])
    op.create_index('uq_approval_states_entity', 'approval_states', ['tenant_id', 'entity_type', 'entity_id'],
                    unique=True, postgresql_where=sa.text('NOT is_deleted'))


def downgrade() -> None:
    op.drop_index('uq_approval_states_entity', table_name='approval_states')
    op.drop_index('ix_approval_states_entity_id', table_name='approval_states')
    op.drop_table('approval_states')
