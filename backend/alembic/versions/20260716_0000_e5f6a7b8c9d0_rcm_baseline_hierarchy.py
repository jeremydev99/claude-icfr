"""rcm baseline 상위 계층 4테이블 + baseline_controls.risk_id FK 전환 (ADR-0027, 2-B-1)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-16 00:00:00.000000+00:00

baseline_processes / baseline_sub_processes / baseline_risks / baseline_risk_categories
신규 생성 (전역 — tenant 비종속, code 전역 unique) + FK 체인 연결.
baseline_controls.risk_id 에 FK(→baseline_risks.id) 제약·인덱스만 추가 (컬럼 자체는 미변경).
기존 processes/sub_processes/risks/risk_categories/controls 테이블은 미변경.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('baseline_processes',
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
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
    op.create_index(op.f('ix_baseline_processes_code'), 'baseline_processes', ['code'], unique=True)

    op.create_table('baseline_sub_processes',
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('process_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.String(length=255), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.String(length=255), nullable=True),
    sa.Column('row_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['process_id'], ['baseline_processes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baseline_sub_processes_code'), 'baseline_sub_processes', ['code'], unique=True)
    op.create_index(op.f('ix_baseline_sub_processes_process_id'), 'baseline_sub_processes', ['process_id'], unique=False)

    op.create_table('baseline_risks',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('assessment_level', sa.String(length=5), nullable=False),
    sa.Column('sub_process_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.String(length=255), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.String(length=255), nullable=True),
    sa.Column('row_version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['sub_process_id'], ['baseline_sub_processes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baseline_risks_code'), 'baseline_risks', ['code'], unique=True)
    op.create_index(op.f('ix_baseline_risks_sub_process_id'), 'baseline_risks', ['sub_process_id'], unique=False)

    op.create_table('baseline_risk_categories',
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
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
    op.create_index(op.f('ix_baseline_risk_categories_code'), 'baseline_risk_categories', ['code'], unique=True)

    # baseline_controls.risk_id → baseline_risks FK 전환 (2-A-1 위임 이행. 컬럼은 그대로, 제약·인덱스만)
    op.create_foreign_key(
        'fk_baseline_controls_risk_id_baseline_risks',
        'baseline_controls', 'baseline_risks', ['risk_id'], ['id'],
    )
    op.create_index(op.f('ix_baseline_controls_risk_id'), 'baseline_controls', ['risk_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_baseline_controls_risk_id'), table_name='baseline_controls')
    op.drop_constraint('fk_baseline_controls_risk_id_baseline_risks', 'baseline_controls', type_='foreignkey')

    op.drop_index(op.f('ix_baseline_risk_categories_code'), table_name='baseline_risk_categories')
    op.drop_table('baseline_risk_categories')
    op.drop_index(op.f('ix_baseline_risks_sub_process_id'), table_name='baseline_risks')
    op.drop_index(op.f('ix_baseline_risks_code'), table_name='baseline_risks')
    op.drop_table('baseline_risks')
    op.drop_index(op.f('ix_baseline_sub_processes_process_id'), table_name='baseline_sub_processes')
    op.drop_index(op.f('ix_baseline_sub_processes_code'), table_name='baseline_sub_processes')
    op.drop_table('baseline_sub_processes')
    op.drop_index(op.f('ix_baseline_processes_code'), table_name='baseline_processes')
    op.drop_table('baseline_processes')
