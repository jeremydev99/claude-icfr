"""어서션 junction baseline/overlay 2테이블 (ADR-0027, 2-B-3)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-16 02:00:00.000000+00:00

baseline_control_assertions(전역 표준 연결) + control_assertion_instances(회사별
add/remove 결정) 신규 생성만 수행. 기존 control_assertions 테이블·데이터는 미변경
(이관은 2-A-2, resolver 연결은 2-B-4).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('baseline_control_assertions',
    sa.Column('baseline_control_id', sa.UUID(), nullable=False),
    sa.Column('baseline_risk_category_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.String(length=255), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.String(length=255), nullable=True),
    sa.Column('row_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['baseline_control_id'], ['baseline_controls.id'], ),
    sa.ForeignKeyConstraint(['baseline_risk_category_id'], ['baseline_risk_categories.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('baseline_control_id', 'baseline_risk_category_id', name='uq_baseline_control_assertions_control_category')
    )
    op.create_index(op.f('ix_baseline_control_assertions_baseline_control_id'), 'baseline_control_assertions', ['baseline_control_id'], unique=False)
    op.create_index(op.f('ix_baseline_control_assertions_baseline_risk_category_id'), 'baseline_control_assertions', ['baseline_risk_category_id'], unique=False)

    op.create_table('control_assertion_instances',
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('control_baseline_id', sa.UUID(), nullable=True),
    sa.Column('control_instance_id', sa.UUID(), nullable=True),
    sa.Column('baseline_risk_category_id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.String(length=255), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.String(length=255), nullable=True),
    sa.Column('row_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['baseline_risk_category_id'], ['baseline_risk_categories.id'], ),
    sa.ForeignKeyConstraint(['control_baseline_id'], ['baseline_controls.id'], ),
    sa.ForeignKeyConstraint(['control_instance_id'], ['control_instances.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'control_baseline_id', 'baseline_risk_category_id', name='uq_control_assertion_instances_tenant_baseline_rc'),
    sa.UniqueConstraint('tenant_id', 'control_instance_id', 'baseline_risk_category_id', name='uq_control_assertion_instances_tenant_instance_rc'),
    sa.CheckConstraint('NOT (control_baseline_id IS NOT NULL AND control_instance_id IS NOT NULL)', name='ck_control_assertion_instances_single_parent')
    )
    op.create_index(op.f('ix_control_assertion_instances_control_baseline_id'), 'control_assertion_instances', ['control_baseline_id'], unique=False)
    op.create_index(op.f('ix_control_assertion_instances_control_instance_id'), 'control_assertion_instances', ['control_instance_id'], unique=False)
    op.create_index(op.f('ix_control_assertion_instances_baseline_risk_category_id'), 'control_assertion_instances', ['baseline_risk_category_id'], unique=False)
    op.create_index(op.f('ix_control_assertion_instances_tenant_id'), 'control_assertion_instances', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_control_assertion_instances_tenant_id'), table_name='control_assertion_instances')
    op.drop_index(op.f('ix_control_assertion_instances_baseline_risk_category_id'), table_name='control_assertion_instances')
    op.drop_index(op.f('ix_control_assertion_instances_control_instance_id'), table_name='control_assertion_instances')
    op.drop_index(op.f('ix_control_assertion_instances_control_baseline_id'), table_name='control_assertion_instances')
    op.drop_table('control_assertion_instances')
    op.drop_index(op.f('ix_baseline_control_assertions_baseline_risk_category_id'), table_name='baseline_control_assertions')
    op.drop_index(op.f('ix_baseline_control_assertions_baseline_control_id'), table_name='baseline_control_assertions')
    op.drop_table('baseline_control_assertions')
