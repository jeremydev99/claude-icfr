"""multitenancy: tenants + user_tenant_access + tenant_id 전면 도입 (ADR-0025)

Revision ID: b1f2c3d4e5a6
Revises: a144dfc162a5
Create Date: 2026-06-26 00:00:00.000000+00:00

데이터 보존 최우선 (ADR-0023): controls·evidence 등 기존 행을 기본 tenant로 귀속.
순서 엄수 — tenant_id 를 nullable 로 먼저 추가 → 기존 행 UPDATE → NOT NULL/FK/index 확정.
한 번에 NOT NULL 로 넣으면 기존 행 때문에 실패하므로 반드시 분리한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b1f2c3d4e5a6'
down_revision: Union[str, None] = 'a144dfc162a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 기본 tenant — app.core.tenant_context.DEFAULT_TENANT_ID 와 일치해야 함
DEFAULT_TENANT_ID = 'd0000000-0000-0000-0000-000000000001'

# tenant_id 를 받을 전 비즈니스 테이블 (AuditedBase 상속). User/Tenant/UserTenantAccess 제외.
BUSINESS_TABLES = [
    'processes', 'sub_processes', 'risks', 'risk_categories', 'controls', 'control_assertions',
    'control_risk_assessments', 'test_runs', 'test_steps', 'test_status_history',
    'deficiencies', 'remediation_plans', 'design_assessments', 'remediation_status_history',
    'evidence_files', 'evidence_links', 'user_roles',
]


def _audit_columns():
    """IdentityBase 공통 감사 컬럼 (server_default 없는 것은 명시)."""
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.Column('row_version', sa.Integer(), nullable=False, server_default=sa.text('1')),
    ]


def upgrade() -> None:
    # 1. tenants 테이블
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        *_audit_columns(),
    )
    op.create_index('ix_tenants_code', 'tenants', ['code'], unique=True)

    # 2. user_tenant_access 테이블
    op.create_table(
        'user_tenant_access',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user'),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant_access'),
    )
    op.create_index('ix_user_tenant_access_user_id', 'user_tenant_access', ['user_id'])
    op.create_index('ix_user_tenant_access_tenant_id', 'user_tenant_access', ['tenant_id'])

    # 3. 기본 tenant 1행 — 기존 데이터 귀속 대상
    op.execute(
        f"""
        INSERT INTO tenants (id, name, code, is_active, is_deleted, row_version, created_at, updated_at)
        VALUES ('{DEFAULT_TENANT_ID}', '사이냅소프트', 'DEFAULT', true, false, 1, now(), now())
        """
    )

    # 4~6. 전 비즈니스 테이블에 tenant_id 도입 (nullable → backfill → NOT NULL/FK/index)
    for t in BUSINESS_TABLES:
        # 4. nullable 로 먼저 추가
        op.add_column(t, sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
        # 5. 기존 행 backfill → 기본 tenant
        op.execute(f"UPDATE {t} SET tenant_id = '{DEFAULT_TENANT_ID}' WHERE tenant_id IS NULL")
        # 6. NOT NULL + FK + index 확정
        op.alter_column(t, 'tenant_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
        op.create_foreign_key(f'fk_{t}_tenant_id', t, 'tenants', ['tenant_id'], ['id'])
        op.create_index(f'ix_{t}_tenant_id', t, ['tenant_id'])

    # 7. 기존 users 를 기본 tenant 에 매핑 (각 user 의 기존 role 이관)
    op.execute(
        f"""
        INSERT INTO user_tenant_access (id, user_id, tenant_id, role, is_deleted, row_version, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, '{DEFAULT_TENANT_ID}', u.role, false, 1, now(), now()
        FROM users u
        WHERE u.is_deleted = false
        """
    )


def downgrade() -> None:
    for t in BUSINESS_TABLES:
        op.drop_index(f'ix_{t}_tenant_id', table_name=t)
        op.drop_constraint(f'fk_{t}_tenant_id', t, type_='foreignkey')
        op.drop_column(t, 'tenant_id')

    op.drop_index('ix_user_tenant_access_tenant_id', table_name='user_tenant_access')
    op.drop_index('ix_user_tenant_access_user_id', table_name='user_tenant_access')
    op.drop_table('user_tenant_access')
    op.drop_index('ix_tenants_code', table_name='tenants')
    op.drop_table('tenants')
