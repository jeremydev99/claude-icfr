"""부서·사용자소속 테이블 추가 (3-1, ADR-0031 §2.8)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-04 00:00:00.000000+00:00

`dept_approver` 가 "통제책임자의 주 소속 부서 책임자"로 유도되려면 부서와 소속이
먼저 있어야 한다(ADR-0031 §2.3). 조직도는 **회사 조직도의 스냅샷**이며 원본은
인사시스템이다 — 발령·개편 로직은 담지 않는다(§2.8).

- `departments` — 평면. `parent_id` 는 계층 개념 보존용으로 두되 초기 전부 NULL.
  `external_code` 는 인사시스템 연동 키로 선반영(현재 미사용).
  `manager_id` 중복 허용 — 본부장이 팀장을 겸임하는 경우가 실재한다.
- `user_departments` — 다중 소속. **주 소속은 사용자당 1건**을 부분 유니크
  인덱스로 DB 가 강제한다(앱 검증만 두면 한 경로만 빠뜨려도 뚫린다).

테넌트 격리는 ADR-0030 §2.3 과 같은 방식 — `(id, tenant_id)` 유니크를 두고
참조 측이 `(fk, tenant_id)` 복합 FK 로 가리킨다. `departments.parent_id` 자기참조도
복합 FK 다: 계층을 실제로 쓰게 되는 시점에 이미 막혀 있어야 한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audited_columns() -> list[sa.Column]:
    """AuditedBase 공통 컬럼 (IdentityBase + TenantMixin)."""
    return [
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(255), nullable=True),
        sa.Column('row_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('tenant_id', PG_UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        'departments',
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('manager_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('parent_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('external_code', sa.String(50), nullable=True),
        *_audited_columns(),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_departments_tenant_name'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_departments_id_tenant'),
    )
    op.create_index('ix_departments_tenant_id', 'departments', ['tenant_id'])
    op.create_index('ix_departments_name', 'departments', ['name'])
    op.create_index('ix_departments_manager_id', 'departments', ['manager_id'])
    op.create_index('ix_departments_parent_id', 'departments', ['parent_id'])
    op.create_index('ix_departments_external_code', 'departments', ['external_code'])
    # 자기참조 복합 FK — 테이블 생성 후에 건다(생성 시점에는 대상 유니크가 아직 없다)
    op.create_foreign_key(
        'fk_departments_parent_tenant', 'departments', 'departments',
        ['parent_id', 'tenant_id'], ['id', 'tenant_id'],
    )

    op.create_table(
        'user_departments',
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('department_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default=sa.false(), nullable=False),
        *_audited_columns(),
        sa.UniqueConstraint('tenant_id', 'user_id', 'department_id', name='uq_user_departments_pair'),
        sa.ForeignKeyConstraint(
            ['department_id', 'tenant_id'], ['departments.id', 'departments.tenant_id'],
            name='fk_user_departments_department_tenant',
        ),
    )
    op.create_index('ix_user_departments_tenant_id', 'user_departments', ['tenant_id'])
    op.create_index('ix_user_departments_user_id', 'user_departments', ['user_id'])
    op.create_index('ix_user_departments_department_id', 'user_departments', ['department_id'])
    # 주 소속은 사용자당 1건 (부분 유니크)
    op.create_index(
        'uq_user_departments_one_primary', 'user_departments', ['tenant_id', 'user_id'],
        unique=True, postgresql_where=sa.text('is_primary'),
    )


def downgrade() -> None:
    op.drop_table('user_departments')
    op.drop_constraint('fk_departments_parent_tenant', 'departments', type_='foreignkey')
    op.drop_table('departments')
