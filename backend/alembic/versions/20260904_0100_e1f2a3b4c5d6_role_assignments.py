"""역할 배정·이해상충 사유·테넌트 정책 테이블 추가 (3-1, ADR-0031 §2.2~2.6)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-04 01:00:00.000000+00:00

- `role_assignments` — 통제 단위 역할 배정. `scope`(process|control) 로 프로세스
  기본값과 통제별 예외를 한 테이블에 담는다. 나누면 해석 로직이 두 벌이 된다.
  **`target_id` 에 FK 를 걸지 않는다** — 대상이 baseline 유래면 `baseline_*.id`,
  회사 add 면 `*_instances.id` 라 참조 테이블이 하나로 정해지지 않는다(정체성 id
  규칙, ADR-0027). FK 를 걸면 add 항목 배정이 막힌다. 존재 검증은 핸들러가 resolver
  결과와 대조한다.
- `conflict_acknowledgements` — 이해상충 사유. 배정이 바뀌어도 지우지 않는다.
  감사에서 "그때 왜 겸직을 허용했는가"를 물으면 이 기록이 답이다(보완통제 증적).
- `tenant_policies` — key-value. 3-2·3-3 에서 항목이 추가되므로 컬럼을 늘려가면
  그때마다 마이그레이션이 필요하다. 스키마 변경은 횟수 자체가 위험이다(ADR-0030).

테넌트 격리는 `AuditedBase` 자동 격리(ADR-0025). `role_assignments` 에는
`(id, tenant_id)` 유니크를 두어 후속(3-2 회차·3-3 증빙)이 복합 FK 로 참조할 수 있게 한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audited_columns() -> list[sa.Column]:
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
        'role_assignments',
        sa.Column('scope', sa.String(10), nullable=False),
        sa.Column('target_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('role_name', sa.String(30), nullable=False),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        *_audited_columns(),
        sa.UniqueConstraint('tenant_id', 'scope', 'target_id', 'role_name',
                            name='uq_role_assignments_target_role'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_role_assignments_id_tenant'),
    )
    for col in ('tenant_id', 'scope', 'target_id', 'role_name', 'user_id'):
        op.create_index(f'ix_role_assignments_{col}', 'role_assignments', [col])

    op.create_table(
        'conflict_acknowledgements',
        sa.Column('scope', sa.String(10), nullable=False),
        sa.Column('target_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('conflict_key', sa.String(60), nullable=False),
        sa.Column('user_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        *_audited_columns(),
    )
    for col in ('tenant_id', 'scope', 'target_id', 'conflict_key', 'user_id'):
        op.create_index(f'ix_conflict_acknowledgements_{col}', 'conflict_acknowledgements', [col])

    op.create_table(
        'tenant_policies',
        sa.Column('policy_key', sa.String(60), nullable=False),
        sa.Column('policy_value', sa.String(200), nullable=False),
        *_audited_columns(),
        sa.UniqueConstraint('tenant_id', 'policy_key', name='uq_tenant_policies_key'),
    )
    op.create_index('ix_tenant_policies_tenant_id', 'tenant_policies', ['tenant_id'])
    op.create_index('ix_tenant_policies_policy_key', 'tenant_policies', ['policy_key'])


def downgrade() -> None:
    op.drop_table('tenant_policies')
    op.drop_table('conflict_acknowledgements')
    op.drop_table('role_assignments')
