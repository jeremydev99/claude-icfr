"""제안 결재 — 제안 묶음·항목 (AI 초안 → 책임관리자 1차 → 마스터 2차, ADR-0038 확장)

Revision ID: 4d6f8a0b2c35
Revises: 9b2c4d6e8f10
Create Date: 2026-10-03 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 2개(`proposals`·`proposal_items`).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = '4d6f8a0b2c35'
down_revision: Union[str, None] = '9b2c4d6e8f10'
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
        'proposals', *_audit_cols(),
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending_review'),
        sa.Column('proposed_by', sa.String(255), nullable=False),
        sa.Column('template_code', sa.String(50), nullable=True),
        sa.Column('template_version', sa.Integer(), nullable=True),
        sa.Column('scoping_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_reason', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
    )
    op.create_table(
        'proposal_items', *_audit_cols(),
        sa.Column('proposal_id', PG_UUID(as_uuid=True), sa.ForeignKey('proposals.id'), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('account_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('statement_type', sa.String(10), nullable=True),
        sa.Column('account_name', sa.String(200), nullable=False),
        sa.Column('group_label', sa.String(200), nullable=True),
        sa.Column('action', sa.String(20), nullable=False, server_default='link'),
        sa.Column('template_account_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('template_name', sa.String(300), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('decided_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('final_template_account_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('final_template_name', sa.String(300), nullable=True),
    )
    op.create_index('ix_proposal_items_proposal_id', 'proposal_items', ['proposal_id'])


def downgrade() -> None:
    op.drop_index('ix_proposal_items_proposal_id', table_name='proposal_items')
    op.drop_table('proposal_items')
    op.drop_table('proposals')
