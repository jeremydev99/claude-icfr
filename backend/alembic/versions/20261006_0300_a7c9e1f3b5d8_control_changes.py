"""통제 변경 결재 — 테이블 2개(추가만)

Revision ID: a7c9e1f3b5d8
Revises: f6b8d0e2a4c7
Create Date: 2026-10-06 03:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 `control_changes`·`control_change_batches`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'a7c9e1f3b5d8'
down_revision: Union[str, None] = 'f6b8d0e2a4c7'
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
        'control_change_batches', *_audit_cols(),
        sa.Column('status', sa.String(20), nullable=False, server_default='review'),
        sa.Column('submitted_by_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('item_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('decided_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
    )
    op.create_table(
        'control_changes', *_audit_cols(),
        sa.Column('control_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('control_code', sa.String(50), nullable=True),
        sa.Column('control_name', sa.String(500), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=False),
        sa.Column('before', sa.JSON(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('author_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dept_approver_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('dept_skipped', sa.String(200), nullable=True),
        sa.Column('dept_decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dept_note', sa.Text(), nullable=True),
        sa.Column('batch_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('admin_decided_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('admin_decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('rejected_by', sa.String(20), nullable=True),
    )
    for col in ('control_id', 'status', 'author_id', 'dept_approver_id', 'batch_id'):
        op.create_index(f'ix_control_changes_{col}', 'control_changes', [col])


def downgrade() -> None:
    for col in ('control_id', 'status', 'author_id', 'dept_approver_id', 'batch_id'):
        op.drop_index(f'ix_control_changes_{col}', table_name='control_changes')
    op.drop_table('control_changes')
    op.drop_table('control_change_batches')
