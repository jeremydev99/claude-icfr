"""평가 회차·대상·활동·승인 테이블 추가 (3-2, ADR-0032 §2.3~2.7)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-04 03:00:00.000000+00:00

- `assessment_cycles` — 회차. `kind`(design|operation)로 두 종류를 가르며 서로 독립이다.
  마감(`closed_*`·`incomplete_reason`)과 최종승인(`approved_*`)을 여기 둔다 —
  **최종승인은 개별 통제가 아니라 회차 전체에 대한 것**이기 때문이다(§2.6).
- `cycle_targets` — 대상 통제 **스냅샷**. 생성 시점 대상을 고정한다.
  조회 시점 계산이면 주기를 바꿨을 때 과거 회차 대상이 달라져 증적이 훼손되고,
  "기록은 있는데 대상 목록에 없는 통제"라는 모순 상태가 생긴다.
- `assessment_activities` — 활동 기록. 수행자·수행시각이 감사추적의 실체다(§2.8).
  같은 통제·회차에 같은 종류가 여러 번 남을 수 있어(재수행·보완) 유니크를 두지 않는다.
- `activity_approvals` — 부서승인/평가자승인. 활동 1건당 단계별 1회.

`control_id` 에 FK 를 걸지 않는다 — baseline 유래면 `baseline_controls.id`, add 면
`control_instances.id` 라 참조 테이블이 하나로 정해지지 않는다(정체성 id 규칙,
ADR-0027). `role_assignments.target_id` 와 같은 사정이며 존재 검증은 핸들러가 한다.

테넌트 격리는 ADR-0030 §2.3 방식 — `(id, tenant_id)` 유니크 + 복합 FK.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audited() -> list[sa.Column]:
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
        'assessment_cycles',
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('frequency', sa.String(12), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(10), nullable=False, server_default='open'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('incomplete_reason', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        *_audited(),
        sa.UniqueConstraint('tenant_id', 'kind', 'name', name='uq_assessment_cycles_kind_name'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_assessment_cycles_id_tenant'),
    )
    for col in ('tenant_id', 'kind', 'frequency', 'status'):
        op.create_index(f'ix_assessment_cycles_{col}', 'assessment_cycles', [col])
    op.alter_column('assessment_cycles', 'status', server_default=None)

    op.create_table(
        'cycle_targets',
        sa.Column('cycle_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('control_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('control_code', sa.String(30), nullable=True),
        *_audited(),
        sa.UniqueConstraint('tenant_id', 'cycle_id', 'control_id', name='uq_cycle_targets_pair'),
        sa.ForeignKeyConstraint(
            ['cycle_id', 'tenant_id'], ['assessment_cycles.id', 'assessment_cycles.tenant_id'],
            name='fk_cycle_targets_cycle_tenant',
        ),
    )
    for col in ('tenant_id', 'cycle_id', 'control_id'):
        op.create_index(f'ix_cycle_targets_{col}', 'cycle_targets', [col])

    op.create_table(
        'assessment_activities',
        sa.Column('cycle_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('control_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('activity_kind', sa.String(24), nullable=False),
        sa.Column('result', sa.String(20), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('performed_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False),
        *_audited(),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_assessment_activities_id_tenant'),
        sa.ForeignKeyConstraint(
            ['cycle_id', 'tenant_id'], ['assessment_cycles.id', 'assessment_cycles.tenant_id'],
            name='fk_assessment_activities_cycle_tenant',
        ),
    )
    for col in ('tenant_id', 'cycle_id', 'control_id', 'activity_kind', 'performed_by_id'):
        op.create_index(f'ix_assessment_activities_{col}', 'assessment_activities', [col])

    op.create_table(
        'activity_approvals',
        sa.Column('activity_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('stage', sa.String(10), nullable=False),
        sa.Column('approved_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        *_audited(),
        sa.UniqueConstraint('tenant_id', 'activity_id', 'stage', name='uq_activity_approvals_stage'),
        sa.ForeignKeyConstraint(
            ['activity_id', 'tenant_id'],
            ['assessment_activities.id', 'assessment_activities.tenant_id'],
            name='fk_activity_approvals_activity_tenant',
        ),
    )
    for col in ('tenant_id', 'activity_id', 'stage', 'approved_by_id'):
        op.create_index(f'ix_activity_approvals_{col}', 'activity_approvals', [col])


def downgrade() -> None:
    op.drop_table('activity_approvals')
    op.drop_table('assessment_activities')
    op.drop_table('cycle_targets')
    op.drop_table('assessment_cycles')
