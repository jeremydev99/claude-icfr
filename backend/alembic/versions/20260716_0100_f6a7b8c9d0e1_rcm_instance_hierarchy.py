"""rcm instance 상위 계층 3테이블 + control_instances.risk_id 이중 FK 전환 (ADR-0027, 2-B-2)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-16 01:00:00.000000+00:00

process_instances / sub_process_instances / risk_instances 신규 생성 (AuditedBase —
tenant 종속, ControlInstance 패턴: unique 2개 + index + 이중 FK check 제약).
control_instances: risk_id(FK→risks) 제거 → risk_baseline_id/risk_instance_id 이중 FK + check.
기존 processes/sub_processes/risks/controls 테이블은 미변경.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('process_instances',
    sa.Column('baseline_process_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
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
    sa.ForeignKeyConstraint(['baseline_process_id'], ['baseline_processes.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'code', name='uq_process_instances_tenant_code'),
    sa.UniqueConstraint('tenant_id', 'baseline_process_id', name='uq_process_instances_tenant_baseline')
    )
    op.create_index(op.f('ix_process_instances_baseline_process_id'), 'process_instances', ['baseline_process_id'], unique=False)
    op.create_index(op.f('ix_process_instances_tenant_id'), 'process_instances', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_process_instances_code'), 'process_instances', ['code'], unique=False)

    op.create_table('sub_process_instances',
    sa.Column('baseline_sub_process_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('process_baseline_id', sa.UUID(), nullable=True),
    sa.Column('process_instance_id', sa.UUID(), nullable=True),
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
    sa.ForeignKeyConstraint(['baseline_sub_process_id'], ['baseline_sub_processes.id'], ),
    sa.ForeignKeyConstraint(['process_baseline_id'], ['baseline_processes.id'], ),
    sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'code', name='uq_sub_process_instances_tenant_code'),
    sa.UniqueConstraint('tenant_id', 'baseline_sub_process_id', name='uq_sub_process_instances_tenant_baseline'),
    sa.CheckConstraint('NOT (process_baseline_id IS NOT NULL AND process_instance_id IS NOT NULL)', name='ck_sub_process_instances_single_parent')
    )
    op.create_index(op.f('ix_sub_process_instances_baseline_sub_process_id'), 'sub_process_instances', ['baseline_sub_process_id'], unique=False)
    op.create_index(op.f('ix_sub_process_instances_process_baseline_id'), 'sub_process_instances', ['process_baseline_id'], unique=False)
    op.create_index(op.f('ix_sub_process_instances_process_instance_id'), 'sub_process_instances', ['process_instance_id'], unique=False)
    op.create_index(op.f('ix_sub_process_instances_tenant_id'), 'sub_process_instances', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_sub_process_instances_code'), 'sub_process_instances', ['code'], unique=False)

    op.create_table('risk_instances',
    sa.Column('baseline_risk_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('assessment_level', sa.String(length=5), nullable=True),
    sa.Column('sub_process_baseline_id', sa.UUID(), nullable=True),
    sa.Column('sub_process_instance_id', sa.UUID(), nullable=True),
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
    sa.ForeignKeyConstraint(['baseline_risk_id'], ['baseline_risks.id'], ),
    sa.ForeignKeyConstraint(['sub_process_baseline_id'], ['baseline_sub_processes.id'], ),
    sa.ForeignKeyConstraint(['sub_process_instance_id'], ['sub_process_instances.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'code', name='uq_risk_instances_tenant_code'),
    sa.UniqueConstraint('tenant_id', 'baseline_risk_id', name='uq_risk_instances_tenant_baseline'),
    sa.CheckConstraint('NOT (sub_process_baseline_id IS NOT NULL AND sub_process_instance_id IS NOT NULL)', name='ck_risk_instances_single_parent')
    )
    op.create_index(op.f('ix_risk_instances_baseline_risk_id'), 'risk_instances', ['baseline_risk_id'], unique=False)
    op.create_index(op.f('ix_risk_instances_sub_process_baseline_id'), 'risk_instances', ['sub_process_baseline_id'], unique=False)
    op.create_index(op.f('ix_risk_instances_sub_process_instance_id'), 'risk_instances', ['sub_process_instance_id'], unique=False)
    op.create_index(op.f('ix_risk_instances_tenant_id'), 'risk_instances', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_risk_instances_code'), 'risk_instances', ['code'], unique=False)

    # control_instances.risk_id(FK→risks) → 이중 FK 전환 (0건 확인 후 진행 — 데이터 이동 없음)
    op.drop_index(op.f('ix_control_instances_risk_id'), table_name='control_instances')
    op.drop_constraint('control_instances_risk_id_fkey', 'control_instances', type_='foreignkey')
    op.drop_column('control_instances', 'risk_id')
    op.add_column('control_instances', sa.Column('risk_baseline_id', sa.UUID(), nullable=True))
    op.add_column('control_instances', sa.Column('risk_instance_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_control_instances_risk_baseline_id_baseline_risks', 'control_instances', 'baseline_risks', ['risk_baseline_id'], ['id'])
    op.create_foreign_key('fk_control_instances_risk_instance_id_risk_instances', 'control_instances', 'risk_instances', ['risk_instance_id'], ['id'])
    op.create_index(op.f('ix_control_instances_risk_baseline_id'), 'control_instances', ['risk_baseline_id'], unique=False)
    op.create_index(op.f('ix_control_instances_risk_instance_id'), 'control_instances', ['risk_instance_id'], unique=False)
    op.create_check_constraint(
        'ck_control_instances_single_parent', 'control_instances',
        'NOT (risk_baseline_id IS NOT NULL AND risk_instance_id IS NOT NULL)',
    )


def downgrade() -> None:
    # control_instances 복원 (risk_id FK→risks — 2-A-1 원형: 제약 이름은 Postgres 자동 명명 규칙)
    op.drop_constraint('ck_control_instances_single_parent', 'control_instances', type_='check')
    op.drop_index(op.f('ix_control_instances_risk_instance_id'), table_name='control_instances')
    op.drop_index(op.f('ix_control_instances_risk_baseline_id'), table_name='control_instances')
    op.drop_constraint('fk_control_instances_risk_instance_id_risk_instances', 'control_instances', type_='foreignkey')
    op.drop_constraint('fk_control_instances_risk_baseline_id_baseline_risks', 'control_instances', type_='foreignkey')
    op.drop_column('control_instances', 'risk_instance_id')
    op.drop_column('control_instances', 'risk_baseline_id')
    op.add_column('control_instances', sa.Column('risk_id', sa.UUID(), nullable=True))
    op.create_foreign_key('control_instances_risk_id_fkey', 'control_instances', 'risks', ['risk_id'], ['id'])
    op.create_index(op.f('ix_control_instances_risk_id'), 'control_instances', ['risk_id'], unique=False)

    op.drop_index(op.f('ix_risk_instances_code'), table_name='risk_instances')
    op.drop_index(op.f('ix_risk_instances_tenant_id'), table_name='risk_instances')
    op.drop_index(op.f('ix_risk_instances_sub_process_instance_id'), table_name='risk_instances')
    op.drop_index(op.f('ix_risk_instances_sub_process_baseline_id'), table_name='risk_instances')
    op.drop_index(op.f('ix_risk_instances_baseline_risk_id'), table_name='risk_instances')
    op.drop_table('risk_instances')
    op.drop_index(op.f('ix_sub_process_instances_code'), table_name='sub_process_instances')
    op.drop_index(op.f('ix_sub_process_instances_tenant_id'), table_name='sub_process_instances')
    op.drop_index(op.f('ix_sub_process_instances_process_instance_id'), table_name='sub_process_instances')
    op.drop_index(op.f('ix_sub_process_instances_process_baseline_id'), table_name='sub_process_instances')
    op.drop_index(op.f('ix_sub_process_instances_baseline_sub_process_id'), table_name='sub_process_instances')
    op.drop_table('sub_process_instances')
    op.drop_index(op.f('ix_process_instances_code'), table_name='process_instances')
    op.drop_index(op.f('ix_process_instances_tenant_id'), table_name='process_instances')
    op.drop_index(op.f('ix_process_instances_baseline_process_id'), table_name='process_instances')
    op.drop_table('process_instances')
