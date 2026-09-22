"""EUC 파일·정보 항목 테이블 (5-1, ADR-0033 정정)

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-22 00:00:00.000000+00:00

구조 (ADR-0033 §2.1 정정):

    RCM 통제 ──1:N── information_items ──N:1── euc_files

- `euc_files` 는 **독립 대상**이다. 엑셀 파일 하나를 여러 통제가 공유할 수 있다
- `information_items.euc_file_id` → `euc_files` 는 **복합 FK** `(euc_file_id, tenant_id)`
  로 테넌트를 넘지 못한다(ADR-0030 §2.3)
- `information_items.control_id` 에는 **FK 를 걸지 않는다.** 통제 id 는 baseline/instance
  두 테이블에 걸친 정체성 id 라 한쪽 FK 가 성립하지 않는다(role_assignments·cycle_targets 와
  같다). 존재 검증은 핸들러가 한다. ⚠️ 그래서 `seed_baseline --reset` 으로 통제 id 가 바뀌면
  연결이 조용히 끊어진다(13.9-27 위험 승계)

**유니크는 처음부터 부분 유니크(`WHERE NOT is_deleted`)다.** 소프트 삭제 행이 키를 점유하면
지웠다 다시 만들 수 없다 — user_roles(13.9-35 ④)·departments(13.9-42)에서 사후에 두 번 고쳤다.

**산출값(파일 중요성·위험 등급·통제 식별 여부)은 컬럼으로 두지 않는다** — 조회 시 계산한다
(ADR-0029 §2.2). 입력값은 파일 복잡도·정보 항목 중요성 두 가지뿐이다(§2.2 정정).

신규 테이블만 만든다. 기존 데이터를 바꾸지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
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
        'euc_files',
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('has_macro', sa.Boolean(), nullable=True),
        sa.Column('complexity', sa.String(20), nullable=True),
        sa.Column('change_frequency', sa.String(10), nullable=True),
        sa.Column('storage_path', sa.String(500), nullable=True),
        sa.Column('managing_department', sa.String(100), nullable=True),
        sa.Column('manager_name', sa.String(100), nullable=True),
        sa.Column('source_risk_rating', sa.String(20), nullable=True),
        sa.Column('source_risk_basis', sa.Text(), nullable=True),
        *_audited_columns(),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_euc_files_id_tenant'),
    )
    op.create_index('ix_euc_files_tenant_id', 'euc_files', ['tenant_id'])
    op.create_index(
        'uq_euc_files_tenant_name', 'euc_files', ['tenant_id', 'name'],
        unique=True, postgresql_where=sa.text('NOT is_deleted'),
    )

    op.create_table(
        'information_items',
        sa.Column('control_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('info_type', sa.String(30), nullable=False),
        sa.Column('importance', sa.String(1), nullable=True),
        sa.Column('euc_file_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('system_name', sa.String(100), nullable=True),
        sa.Column('itgc_in_scope', sa.String(10), nullable=True),
        sa.Column('source_data', sa.Text(), nullable=True),
        sa.Column('report_logic', sa.Text(), nullable=True),
        sa.Column('input_parameter', sa.Text(), nullable=True),
        sa.Column('source_data_review', sa.Text(), nullable=True),
        sa.Column('report_logic_control', sa.Text(), nullable=True),
        sa.Column('input_parameter_review', sa.Text(), nullable=True),
        sa.Column('design_assessment_result', sa.Text(), nullable=True),
        *_audited_columns(),
        sa.ForeignKeyConstraint(
            ['euc_file_id', 'tenant_id'], ['euc_files.id', 'euc_files.tenant_id'],
            name='fk_information_items_euc_file_tenant',
        ),
    )
    op.create_index('ix_information_items_tenant_id', 'information_items', ['tenant_id'])
    op.create_index('ix_information_items_control_id', 'information_items', ['control_id'])
    op.create_index('ix_information_items_euc_file_id', 'information_items', ['euc_file_id'])
    op.create_index(
        'uq_information_items_control_name', 'information_items',
        ['tenant_id', 'control_id', 'name'],
        unique=True, postgresql_where=sa.text('NOT is_deleted'),
    )


def downgrade() -> None:
    op.drop_table('information_items')
    op.drop_table('euc_files')
