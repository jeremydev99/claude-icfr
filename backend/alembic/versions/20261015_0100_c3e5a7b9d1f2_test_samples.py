"""테스트 표본 — RCM 테스트 방법 칸 + 활동 작성·제출 + 활동 샘플 (13.9-129)

Revision ID: c3e5a7b9d1f2
Revises: b8d0f2a4c6e8
Create Date: 2026-10-15 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.**
- `baseline_controls`·`control_instances`: 테스트 방법·모집단·표본수·테스트 절차 (nullable). 원천 엑셀
  '테스트방법' 영역이며 그동안 업로드 때 버려졌다. 표본수는 감사인과 협의한 값 = 운영평가 필요 샘플 수.
- `assessment_activities`: `status`(draft/submitted, 기존 행은 server_default 'submitted' — 지금까지는 기록 즉시
  확정이었으므로 의미가 같다), `submitted_at`, `required_samples`(제출 시점 필요 수), 테스트 방법·모집단·절차.
- `activity_samples`(신규): 활동 1건의 샘플 한 줄씩. 증빙은 `evidence_links`(linked_entity_type='sample')로 잇는다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = 'c3e5a7b9d1f2'
down_revision: str | None = 'b8d0f2a4c6e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEST_COLS = (
    ('test_methods', lambda: sa.String(60)),
    ('population', sa.Text),
    ('sample_size', sa.Integer),
    ('test_procedure', sa.Text),
)


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
    for table in ('baseline_controls', 'control_instances'):
        for name, typ in _TEST_COLS:
            op.add_column(table, sa.Column(name, typ(), nullable=True))

    op.add_column('assessment_activities',
                  sa.Column('status', sa.String(10), nullable=False, server_default='submitted'))
    op.add_column('assessment_activities', sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assessment_activities', sa.Column('required_samples', sa.Integer(), nullable=True))
    op.add_column('assessment_activities', sa.Column('test_methods', sa.String(60), nullable=True))
    op.add_column('assessment_activities', sa.Column('population', sa.Text(), nullable=True))
    op.add_column('assessment_activities', sa.Column('procedure', sa.Text(), nullable=True))
    op.create_index('ix_assessment_activities_status', 'assessment_activities', ['status'])

    op.create_table(
        'activity_samples',
        sa.Column('activity_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(200), nullable=True),
        sa.Column('sampled_on', sa.Date(), nullable=True),
        sa.Column('result', sa.String(10), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        *_audited(),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_activity_samples_id_tenant'),
        sa.ForeignKeyConstraint(
            ['activity_id', 'tenant_id'],
            ['assessment_activities.id', 'assessment_activities.tenant_id'],
            name='fk_activity_samples_activity_tenant',
        ),
    )
    op.create_index('ix_activity_samples_activity_id', 'activity_samples', ['activity_id'])
    op.create_index('ix_activity_samples_tenant_id', 'activity_samples', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_activity_samples_tenant_id', table_name='activity_samples')
    op.drop_index('ix_activity_samples_activity_id', table_name='activity_samples')
    op.drop_table('activity_samples')
    op.drop_index('ix_assessment_activities_status', table_name='assessment_activities')
    for name in ('procedure', 'population', 'test_methods', 'required_samples', 'submitted_at', 'status'):
        op.drop_column('assessment_activities', name)
    for table in ('control_instances', 'baseline_controls'):
        for name, _ in reversed(_TEST_COLS):
            op.drop_column(table, name)
