"""회계연도 RCM 확정 — rcm_fiscal_years·rcm_snapshots (ADR-0038 2-5)

Revision ID: e3a5c7b9d1f4
Revises: c1e3a5b7d9f2
Create Date: 2026-10-08 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** 새 테이블 2개. 확정이라는 개념이 처음 생기므로 옮길 기존 데이터가 없다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = 'e3a5c7b9d1f4'
down_revision: str | None = 'c1e3a5b7d9f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_cols() -> list:
    return [
        sa.Column('id', PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', PG_UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', sa.String(255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.String(255), nullable=True),
        sa.Column('row_version', sa.Integer(), server_default='1', nullable=False),
    ]


def upgrade() -> None:
    op.create_table('rcm_fiscal_years', *_audit_cols(),
                    sa.Column('fiscal_year', sa.Integer(), nullable=False))
    op.create_index('uq_rcm_fiscal_years_year', 'rcm_fiscal_years', ['tenant_id', 'fiscal_year'], unique=True,
                    postgresql_where=sa.text('NOT is_deleted'))
    op.create_table('rcm_snapshots', *_audit_cols(),
                    sa.Column('rcm_year_id', PG_UUID(as_uuid=True), sa.ForeignKey('rcm_fiscal_years.id'), nullable=False),
                    sa.Column('fiscal_year', sa.Integer(), nullable=False),
                    sa.Column('version', sa.Integer(), nullable=False),
                    sa.Column('snapshot', sa.JSON(), nullable=False),
                    sa.Column('control_count', sa.Integer(), nullable=False),
                    sa.Column('confirmed_by_id', PG_UUID(as_uuid=True), nullable=True),
                    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_rcm_snapshots_rcm_year_id', 'rcm_snapshots', ['rcm_year_id'])


def downgrade() -> None:
    op.drop_index('ix_rcm_snapshots_rcm_year_id', table_name='rcm_snapshots')
    op.drop_table('rcm_snapshots')
    op.drop_index('uq_rcm_fiscal_years_year', table_name='rcm_fiscal_years')
    op.drop_table('rcm_fiscal_years')
