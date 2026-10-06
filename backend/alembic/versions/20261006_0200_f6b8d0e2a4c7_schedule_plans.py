"""일정관리 — 표준 일정·회계연도 일정안·항목(추가만)

Revision ID: f6b8d0e2a4c7
Revises: e5a7c9d1f3b6
Create Date: 2026-10-06 02:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 3개(`schedule_templates`·`schedule_plans`·`schedule_items`).
표준 일정은 저장된 것이 없으면 코드의 내장 8개를 쓴다 — 시드를 넣지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'f6b8d0e2a4c7'
down_revision: Union[str, None] = 'e5a7c9d1f3b6'
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
        'schedule_templates', *_audit_cols(),
        sa.Column('code', sa.String(40), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(20), nullable=False, server_default='other'),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tasks', sa.JSON(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_table(
        'schedule_plans', *_audit_cols(),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('approval_line', sa.JSON(), nullable=False),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('approvals', sa.JSON(), nullable=False),
        sa.Column('requested_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('request_note', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('returned_reason', sa.Text(), nullable=True),
    )
    op.create_index('uq_schedule_plans_year', 'schedule_plans', ['tenant_id', 'fiscal_year'], unique=True,
                    postgresql_where=sa.text('NOT is_deleted'))
    op.create_table(
        'schedule_items', *_audit_cols(),
        sa.Column('plan_id', PG_UUID(as_uuid=True), sa.ForeignKey('schedule_plans.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False, server_default='custom'),
        sa.Column('template_code', sa.String(40), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('category', sa.String(20), nullable=False, server_default='other'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tasks', sa.JSON(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_schedule_items_plan_id', 'schedule_items', ['plan_id'])


def downgrade() -> None:
    op.drop_index('ix_schedule_items_plan_id', table_name='schedule_items')
    op.drop_table('schedule_items')
    op.drop_index('uq_schedule_plans_year', table_name='schedule_plans')
    op.drop_table('schedule_plans')
    op.drop_table('schedule_templates')
