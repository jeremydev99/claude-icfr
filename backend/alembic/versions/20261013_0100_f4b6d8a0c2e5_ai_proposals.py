"""AI 제안 기록 — ai_proposals (ADR-0042)

Revision ID: f4b6d8a0c2e5
Revises: e3a5c7b9d1f4
Create Date: 2026-10-13 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 1개. AI 제안이라는 개념이 처음 생기므로 옮길 기존 데이터가 없다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = 'f4b6d8a0c2e5'
down_revision: str | None = 'e3a5c7b9d1f4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ai_proposals',
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
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('target_type', sa.String(40), nullable=False),
        sa.Column('target_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('fiscal_year', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='proposed'),
        sa.Column('engine', sa.String(80), nullable=False),
        sa.Column('trigger', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('basis', sa.JSON(), nullable=False),
        sa.Column('proposed', sa.JSON(), nullable=False),
        sa.Column('adopted_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('adopted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('adopted_changes', sa.JSON(), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
    )
    op.create_index('ix_ai_proposals_target', 'ai_proposals', ['target_type', 'target_id'])


def downgrade() -> None:
    op.drop_index('ix_ai_proposals_target', table_name='ai_proposals')
    op.drop_table('ai_proposals')
