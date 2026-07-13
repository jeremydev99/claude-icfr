"""rcm baseline/instance 신규 테이블 (ADR-0027, 2-A-1)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-13 00:00:00.000000+00:00

baseline_controls(전역 표준) + control_instances(회사별 결정) 신규 생성만 수행.
기존 controls 테이블·데이터는 미변경 (이관은 2-A-2).
baseline_controls.risk_id 는 FK 없는 nullable UUID (2-B baseline_risks 에서 FK 전환).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('baseline_controls',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('risk_id', sa.UUID(), nullable=True),
    sa.Column('objective', sa.Text(), nullable=True),
    sa.Column('owner_name', sa.String(length=200), nullable=True),
    sa.Column('is_key_control', sa.Boolean(), nullable=False),
    sa.Column('preventive_detective', sa.String(length=2), nullable=False),
    sa.Column('auto_manual', sa.String(length=2), nullable=False),
    sa.Column('activity_approval', sa.Boolean(), nullable=False),
    sa.Column('activity_verification', sa.Boolean(), nullable=False),
    sa.Column('activity_physical', sa.Boolean(), nullable=False),
    sa.Column('activity_master_data', sa.Boolean(), nullable=False),
    sa.Column('activity_reconciliation', sa.Boolean(), nullable=False),
    sa.Column('activity_supervision', sa.Boolean(), nullable=False),
    sa.Column('related_accounts', sa.Text(), nullable=True),
    sa.Column('frequency', sa.String(length=2), nullable=False),
    sa.Column('ipe_relevant', sa.String(length=5), nullable=False),
    sa.Column('related_systems', sa.Text(), nullable=True),
    sa.Column('euc_description', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.String(length=255), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.String(length=255), nullable=True),
    sa.Column('row_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baseline_controls_code'), 'baseline_controls', ['code'], unique=True)

    op.create_table('control_instances',
    sa.Column('baseline_control_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=True),
    sa.Column('name', sa.String(length=500), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('risk_id', sa.UUID(), nullable=True),
    sa.Column('objective', sa.Text(), nullable=True),
    sa.Column('owner_name', sa.String(length=200), nullable=True),
    sa.Column('is_key_control', sa.Boolean(), nullable=True),
    sa.Column('preventive_detective', sa.String(length=2), nullable=True),
    sa.Column('auto_manual', sa.String(length=2), nullable=True),
    sa.Column('activity_approval', sa.Boolean(), nullable=True),
    sa.Column('activity_verification', sa.Boolean(), nullable=True),
    sa.Column('activity_physical', sa.Boolean(), nullable=True),
    sa.Column('activity_master_data', sa.Boolean(), nullable=True),
    sa.Column('activity_reconciliation', sa.Boolean(), nullable=True),
    sa.Column('activity_supervision', sa.Boolean(), nullable=True),
    sa.Column('related_accounts', sa.Text(), nullable=True),
    sa.Column('frequency', sa.String(length=2), nullable=True),
    sa.Column('ipe_relevant', sa.String(length=5), nullable=True),
    sa.Column('related_systems', sa.Text(), nullable=True),
    sa.Column('euc_description', sa.Text(), nullable=True),
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
    sa.ForeignKeyConstraint(['baseline_control_id'], ['baseline_controls.id'], ),
    sa.ForeignKeyConstraint(['risk_id'], ['risks.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'code', name='uq_control_instances_tenant_code'),
    sa.UniqueConstraint('tenant_id', 'baseline_control_id', name='uq_control_instances_tenant_baseline')
    )
    op.create_index(op.f('ix_control_instances_baseline_control_id'), 'control_instances', ['baseline_control_id'], unique=False)
    op.create_index(op.f('ix_control_instances_risk_id'), 'control_instances', ['risk_id'], unique=False)
    op.create_index(op.f('ix_control_instances_tenant_id'), 'control_instances', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_control_instances_code'), 'control_instances', ['code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_control_instances_code'), table_name='control_instances')
    op.drop_index(op.f('ix_control_instances_tenant_id'), table_name='control_instances')
    op.drop_index(op.f('ix_control_instances_risk_id'), table_name='control_instances')
    op.drop_index(op.f('ix_control_instances_baseline_control_id'), table_name='control_instances')
    op.drop_table('control_instances')
    op.drop_index(op.f('ix_baseline_controls_code'), table_name='baseline_controls')
    op.drop_table('baseline_controls')
