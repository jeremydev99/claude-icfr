"""재무제표·계정 트리 — 계정 마스터·재무제표 헤더·금액 행·상태 이력 (8-A, ADR-0037)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-28 01:00:00.000000+00:00

**신규 테이블 4개만 만든다. 기존 테이블·데이터를 바꾸지 않는다.** 스코핑(`scoping_*`)과 병행 신규
구축이며, 스코핑이 이 구조를 쓰도록 바꾸는 것은 8-E 다.

- `fs_accounts` — 회사 계정 마스터. 트리는 `parent_id` + `sort_order`. 부모는 `(parent_id, tenant_id)`
  복합 FK 로 같은 테넌트만. 자기 참조는 CHECK 로, 자손 참조(순환)는 서비스의 재귀 CTE 로 막는다
- `fs_statements` — 회계연도 × 종류 × 연결/별도. 단위·통화·허용 오차
- `fs_amounts` — 헤더 × 계정 금액. `Numeric(20, 2)`, 원본 보존 컬럼(`raw_*`)
- `fs_statement_status_events` — 확정·재오픈 이력

하위 참조는 전부 `(x_id, tenant_id)` 복합 FK(ADR-0030 §2.3). 유니크는 처음부터 부분 유니크.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE = sa.text('NOT is_deleted')


def _amount(name: str, nullable: bool = True, **kw) -> sa.Column:
    return sa.Column(name, sa.Numeric(20, 2), nullable=nullable, **kw)


def _audited_columns() -> list[sa.Column]:
    """AuditedBase 공통 컬럼 (IdentityBase + tenant_id)."""
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


def _statement_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(['statement_id', 'tenant_id'], ['fs_statements.id', 'fs_statements.tenant_id'],
                                   name=f'fk_{table}_statement_tenant')


def upgrade() -> None:
    op.create_table(
        'fs_accounts',
        sa.Column('statement_type', sa.String(10), nullable=False),
        sa.Column('parent_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('section', sa.String(30), nullable=False),
        sa.Column('is_subtotal', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('rollup_sign', sa.SmallInteger(), server_default='1', nullable=False),
        sa.Column('valid_from_year', sa.Integer(), nullable=True),
        sa.Column('valid_to_year', sa.Integer(), nullable=True),
        *_audited_columns(),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_fs_accounts_id_tenant'),
        sa.ForeignKeyConstraint(['parent_id', 'tenant_id'], ['fs_accounts.id', 'fs_accounts.tenant_id'],
                                name='fk_fs_accounts_parent_tenant'),
        sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name='ck_fs_accounts_not_self_parent'),
        sa.CheckConstraint('rollup_sign IN (1, -1)', name='ck_fs_accounts_rollup_sign'),
        sa.CheckConstraint('valid_from_year IS NULL OR valid_to_year IS NULL OR valid_from_year <= valid_to_year',
                           name='ck_fs_accounts_valid_range'),
    )
    op.create_index('ix_fs_accounts_tenant_id', 'fs_accounts', ['tenant_id'])
    op.create_index('ix_fs_accounts_parent_id', 'fs_accounts', ['parent_id'])
    op.create_index('uq_fs_accounts_code', 'fs_accounts', ['tenant_id', 'code'], unique=True,
                    postgresql_where=sa.text('NOT is_deleted AND code IS NOT NULL'))

    op.create_table(
        'fs_statements',
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('statement_type', sa.String(10), nullable=False),
        sa.Column('basis', sa.String(20), nullable=False),
        sa.Column('unit', sa.Integer(), server_default='1', nullable=False),
        sa.Column('currency', sa.String(3), server_default='KRW', nullable=False),
        _amount('tolerance', nullable=False, server_default='0'),
        sa.Column('status', sa.String(10), server_default='draft', nullable=False),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finalized_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('source_kind', sa.String(30), nullable=True),
        sa.Column('source_filename', sa.String(300), nullable=True),
        sa.Column('source_sheet', sa.String(200), nullable=True),
        *_audited_columns(),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_fs_statements_id_tenant'),
        sa.CheckConstraint('tolerance >= 0', name='ck_fs_statements_tolerance'),
    )
    op.create_index('ix_fs_statements_tenant_id', 'fs_statements', ['tenant_id'])
    op.create_index('uq_fs_statements_year_type_basis', 'fs_statements',
                    ['tenant_id', 'fiscal_year', 'statement_type', 'basis'], unique=True,
                    postgresql_where=_ACTIVE)

    op.create_table(
        'fs_amounts',
        sa.Column('statement_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', PG_UUID(as_uuid=True), nullable=False),
        _amount('amount'),
        sa.Column('raw_row_no', sa.Integer(), nullable=True),
        sa.Column('raw_label', sa.String(300), nullable=True),
        sa.Column('raw_indent', sa.Integer(), nullable=True),
        sa.Column('raw_value', sa.String(100), nullable=True),
        sa.Column('raw_meta', sa.JSON(), nullable=True),
        *_audited_columns(),
        _statement_fk('fs_amounts'),
        sa.ForeignKeyConstraint(['account_id', 'tenant_id'], ['fs_accounts.id', 'fs_accounts.tenant_id'],
                                name='fk_fs_amounts_account_tenant'),
    )
    op.create_index('ix_fs_amounts_tenant_id', 'fs_amounts', ['tenant_id'])
    op.create_index('ix_fs_amounts_statement_id', 'fs_amounts', ['statement_id'])
    op.create_index('ix_fs_amounts_account_id', 'fs_amounts', ['account_id'])
    op.create_index('uq_fs_amounts_statement_account', 'fs_amounts',
                    ['tenant_id', 'statement_id', 'account_id'], unique=True, postgresql_where=_ACTIVE)

    op.create_table(
        'fs_statement_status_events',
        sa.Column('statement_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('from_status', sa.String(10), nullable=False),
        sa.Column('to_status', sa.String(10), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('actor_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        _amount('tolerance'),
        sa.Column('skipped_count', sa.Integer(), nullable=True),
        sa.Column('tolerance_diffs', sa.JSON(), nullable=True),
        *_audited_columns(),
        _statement_fk('fs_statement_status_events'),
    )
    op.create_index('ix_fs_statement_status_events_tenant_id', 'fs_statement_status_events', ['tenant_id'])
    op.create_index('ix_fs_statement_status_events_statement_id', 'fs_statement_status_events',
                    ['statement_id'])


def downgrade() -> None:
    op.drop_table('fs_statement_status_events')
    op.drop_table('fs_amounts')
    op.drop_table('fs_statements')
    op.drop_table('fs_accounts')
