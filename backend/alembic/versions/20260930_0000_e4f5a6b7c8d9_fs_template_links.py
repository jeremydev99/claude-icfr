"""재무제표 8-C — 회사 계정 ↔ 스코핑 템플릿 계정 링크 (ADR-0037 §4)

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-30 00:00:00.000000+00:00

**신규 테이블 1개만 만든다. 기존 테이블·데이터를 바꾸지 않는다.** 스코핑(`scoping_*`)은 이 링크를 아직
쓰지 않는다(8-E).

- `fs_template_links` — 사람이 확인한 링크만. 근거(exact/normalized/manual)·확인자·시각.
  회사 계정은 `(account_id, tenant_id)` 복합 FK(ADR-0030 §2.3), 템플릿 계정은 전역 테이블이라 단일 FK.
  활성 링크는 회사 계정 × 템플릿 버전당 1개(부분 유니크).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audited_columns() -> list[sa.Column]:
    """AuditedBase 공통 컬럼 (IdentityBase + tenant_id) — 8-A 마이그레이션과 같다."""
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
        'fs_template_links',
        sa.Column('account_id', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('template_account_id', PG_UUID(as_uuid=True), sa.ForeignKey('scoping_template_accounts.id'),
                  nullable=False),
        sa.Column('template_code', sa.String(50), nullable=False),
        sa.Column('template_version', sa.Integer(), nullable=False),
        sa.Column('basis', sa.String(20), nullable=False),
        sa.Column('confirmed_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        *_audited_columns(),
        sa.ForeignKeyConstraint(['account_id', 'tenant_id'], ['fs_accounts.id', 'fs_accounts.tenant_id'],
                                name='fk_fs_template_links_account_tenant'),
        sa.CheckConstraint("basis IN ('exact', 'normalized', 'manual')", name='ck_fs_template_links_basis'),
    )
    op.create_index('ix_fs_template_links_tenant_id', 'fs_template_links', ['tenant_id'])
    op.create_index('ix_fs_template_links_account_id', 'fs_template_links', ['account_id'])
    op.create_index('ix_fs_template_links_template_account_id', 'fs_template_links', ['template_account_id'])
    op.create_index('uq_fs_template_links_account_version', 'fs_template_links',
                    ['tenant_id', 'account_id', 'template_code', 'template_version'], unique=True,
                    postgresql_where=sa.text('NOT is_deleted'))


def downgrade() -> None:
    op.drop_index('uq_fs_template_links_account_version', table_name='fs_template_links')
    op.drop_index('ix_fs_template_links_template_account_id', table_name='fs_template_links')
    op.drop_index('ix_fs_template_links_account_id', table_name='fs_template_links')
    op.drop_index('ix_fs_template_links_tenant_id', table_name='fs_template_links')
    op.drop_table('fs_template_links')
