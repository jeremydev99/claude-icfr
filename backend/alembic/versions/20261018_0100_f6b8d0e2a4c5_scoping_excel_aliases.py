"""스코핑 엑셀 직접 연결 기억 — scoping_excel_aliases (13.9-146)

Revision ID: f6b8d0e2a4c5
Revises: e5a7c9d1f3b4
Create Date: 2026-10-18 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.**
- `scoping_excel_aliases`(신규): 스코핑 엑셀 갱신 업로드에서 사람이 고른 연결(엑셀 행 → 스코핑 계정)을 **이름 기준**으로 기억한다.
  계정 id 가 아니라 표·이름·구분으로 저장해 해가 바뀌어 계정 행이 새로 만들어져도 찾아간다. 같은 엑셀 키는 한 줄(덮어쓴다).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = 'f6b8d0e2a4c5'
down_revision: str | None = 'e5a7c9d1f3b4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'scoping_excel_aliases',
        sa.Column('statement_type', sa.String(10), nullable=False),
        sa.Column('excel_name_key', sa.String(200), nullable=False),
        sa.Column('excel_group_key', sa.String(200), nullable=False, server_default=''),
        sa.Column('account_name', sa.String(200), nullable=False),
        sa.Column('account_group', sa.String(200), nullable=True),
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
        sa.UniqueConstraint('id', 'tenant_id', name='uq_scoping_excel_aliases_id_tenant'),
        sa.UniqueConstraint('tenant_id', 'statement_type', 'excel_name_key', 'excel_group_key',
                            name='uq_scoping_excel_aliases_key'),
    )
    op.create_index('ix_scoping_excel_aliases_tenant_id', 'scoping_excel_aliases', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_scoping_excel_aliases_tenant_id', table_name='scoping_excel_aliases')
    op.drop_table('scoping_excel_aliases')
