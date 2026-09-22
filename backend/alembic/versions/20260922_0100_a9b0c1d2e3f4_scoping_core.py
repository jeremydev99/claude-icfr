"""스코핑 코어 — 전역 템플릿 + 테넌트 스코핑 (6-1, ADR-0034)

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-22 01:00:00.000000+00:00

두 계층을 만든다.

- **전역 템플릿**(`IdentityBase`, tenant_id 없음): scoping_templates / _texts / _accounts.
  제품 콘텐츠다. 테넌트 격리 대상이 아니다(ADR-0030 §2.4 의 템플릿 계층)
- **테넌트 스코핑**(`AuditedBase`): scopings 와 하위 7개. 하위는 전부 `(scoping_id, tenant_id)`
  복합 FK 로 테넌트를 넘지 못한다(ADR-0030 §2.3)

`scoping_field_origins` 는 **대상이 다형**(scoping/text/account/benchmark)이라 대상 FK 를 걸 수 없다.
스코핑에 대한 복합 FK 만 걸고, 대상 존재 검증은 핸들러가 한다.

유니크는 **처음부터 부분 유니크(`WHERE NOT is_deleted`)** — 13.9-35 ④·13.9-42 를 반복하지 않는다.
계산 결론은 컬럼으로 두지 않는다(ADR-0029 §2.2). **확정 스냅샷(`confirmed_snapshot`)만 저장한다.**

금액은 BigInteger(원), 비율은 Numeric — float 를 쓰지 않는다(원천과 한 원도 다르면 안 된다).

신규 테이블만 만든다. 기존 데이터를 바꾸지 않는다. 템플릿 데이터는 이 마이그레이션이 넣지 않는다 —
`python -m seeds.seed_scoping_template` 가 넣는다(원천 엑셀을 읽어야 해서 마이그레이션에 두지 않는다).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE = sa.text('NOT is_deleted')


def _identity_columns() -> list[sa.Column]:
    """IdentityBase 공통 컬럼 (tenant_id 없음)."""
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
    ]


def _audited_columns() -> list[sa.Column]:
    """AuditedBase 공통 컬럼 (IdentityBase + tenant_id)."""
    return _identity_columns() + [
        sa.Column('tenant_id', PG_UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
    ]


def _scoping_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(['scoping_id', 'tenant_id'], ['scopings.id', 'scopings.tenant_id'],
                                   name=f'fk_{table}_scoping_tenant')


def _child(table: str, *cols: sa.Column) -> None:
    op.create_table(table, sa.Column('scoping_id', PG_UUID(as_uuid=True), nullable=False),
                    *cols, *_audited_columns(), _scoping_fk(table))
    op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])
    op.create_index(f'ix_{table}_scoping_id', table, ['scoping_id'])


def upgrade() -> None:
    # ── 전역 템플릿 ──
    op.create_table(
        'scoping_templates',
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('source', sa.String(300), nullable=True),
        sa.Column('default_benchmark', sa.String(30), nullable=False),
        sa.Column('default_rates', sa.JSON(), nullable=False),
        sa.Column('default_smt_rate', sa.String(10), nullable=False),
        *_identity_columns(),
    )
    op.create_index('uq_scoping_templates_code_version', 'scoping_templates', ['code', 'version'],
                    unique=True, postgresql_where=_ACTIVE)

    op.create_table(
        'scoping_template_texts',
        sa.Column('template_id', PG_UUID(as_uuid=True), sa.ForeignKey('scoping_templates.id'), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('title', sa.String(300), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        *_identity_columns(),
    )
    op.create_index('ix_scoping_template_texts_template_id', 'scoping_template_texts', ['template_id'])
    op.create_index('uq_scoping_template_texts_key', 'scoping_template_texts', ['template_id', 'key'],
                    unique=True, postgresql_where=_ACTIVE)

    op.create_table(
        'scoping_template_accounts',
        sa.Column('template_id', PG_UUID(as_uuid=True), sa.ForeignKey('scoping_templates.id'), nullable=False),
        sa.Column('statement_type', sa.String(10), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('group_label', sa.String(200), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('ratings', sa.JSON(), nullable=False),
        sa.Column('qual_basis', sa.Text(), nullable=True),
        sa.Column('manual_conclusion', sa.String(1), nullable=True),
        sa.Column('manual_reason', sa.Text(), nullable=True),
        *_identity_columns(),
    )
    op.create_index('ix_scoping_template_accounts_template_id', 'scoping_template_accounts', ['template_id'])

    # ── 테넌트 스코핑 ──
    op.create_table(
        'scopings',
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('template_code', sa.String(50), nullable=True),
        sa.Column('template_version', sa.Integer(), nullable=True),
        sa.Column('selected_benchmark', sa.String(30), nullable=False),
        sa.Column('smt_rate', sa.Numeric(7, 4), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('confirm_reason', sa.Text(), nullable=True),
        sa.Column('confirm_badge_count', sa.Integer(), nullable=True),
        sa.Column('confirmed_snapshot', sa.JSON(), nullable=True),
        sa.Column('review_auditor', sa.String(200), nullable=True),
        sa.Column('review_date', sa.Date(), nullable=True),
        sa.Column('review_opinion', sa.Text(), nullable=True),
        sa.Column('review_evidence_ref', sa.Text(), nullable=True),
        *_audited_columns(),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_scopings_id_tenant'),
    )
    op.create_index('ix_scopings_tenant_id', 'scopings', ['tenant_id'])
    op.create_index('uq_scopings_tenant_year', 'scopings', ['tenant_id', 'fiscal_year'],
                    unique=True, postgresql_where=_ACTIVE)

    _child('scoping_benchmarks',
           sa.Column('kind', sa.String(30), nullable=False),
           sa.Column('base_amount', sa.BigInteger(), nullable=True),
           sa.Column('rate', sa.Numeric(9, 6), nullable=True))
    op.create_index('uq_scoping_benchmarks_kind', 'scoping_benchmarks', ['tenant_id', 'scoping_id', 'kind'],
                    unique=True, postgresql_where=_ACTIVE)

    _child('scoping_adjustments',
           sa.Column('amount', sa.BigInteger(), nullable=False),
           sa.Column('reason', sa.Text(), nullable=False))

    _child('scoping_texts',
           sa.Column('key', sa.String(100), nullable=False),
           sa.Column('title', sa.String(300), nullable=True),
           sa.Column('body', sa.Text(), nullable=False),
           sa.Column('sort_order', sa.Integer(), nullable=False))
    op.create_index('uq_scoping_texts_key', 'scoping_texts', ['tenant_id', 'scoping_id', 'key'],
                    unique=True, postgresql_where=_ACTIVE)

    _child('scoping_accounts',
           sa.Column('statement_type', sa.String(10), nullable=False),
           sa.Column('sort_order', sa.Integer(), nullable=False),
           sa.Column('group_label', sa.String(200), nullable=True),
           sa.Column('name', sa.String(200), nullable=False),
           sa.Column('current_amount', sa.BigInteger(), nullable=True),
           sa.Column('prior_amount', sa.BigInteger(), nullable=True),
           sa.Column('ratings', sa.JSON(), nullable=False),
           sa.Column('qual_basis', sa.Text(), nullable=True),
           sa.Column('manual_conclusion', sa.String(1), nullable=True),
           sa.Column('manual_reason', sa.Text(), nullable=True))

    _child('scoping_status_history',
           sa.Column('from_status', sa.String(20), nullable=False),
           sa.Column('to_status', sa.String(20), nullable=False),
           sa.Column('reason', sa.Text(), nullable=True),
           sa.Column('actor_id', PG_UUID(as_uuid=True), nullable=False),
           sa.Column('badge_count', sa.Integer(), nullable=True),
           sa.Column('snapshot', sa.JSON(), nullable=True))

    _child('scoping_field_origins',
           sa.Column('target_type', sa.String(20), nullable=False),
           sa.Column('target_id', PG_UUID(as_uuid=True), nullable=False),
           sa.Column('field', sa.String(50), nullable=False),
           sa.Column('status', sa.String(20), nullable=False),
           sa.Column('template_version', sa.Integer(), nullable=True))
    op.create_index('ix_scoping_field_origins_target_id', 'scoping_field_origins', ['target_id'])
    op.create_index('uq_scoping_field_origins_field', 'scoping_field_origins',
                    ['tenant_id', 'target_type', 'target_id', 'field'], unique=True, postgresql_where=_ACTIVE)


def downgrade() -> None:
    for t in ('scoping_field_origins', 'scoping_status_history', 'scoping_accounts', 'scoping_texts',
              'scoping_adjustments', 'scoping_benchmarks', 'scopings',
              'scoping_template_accounts', 'scoping_template_texts', 'scoping_templates'):
        op.drop_table(t)
