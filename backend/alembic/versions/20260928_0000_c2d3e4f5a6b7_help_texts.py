"""매뉴얼 패널 문구 저장 — help_texts (7-A, ADR-0035)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-28 00:00:00.000000+00:00

**tenant 비종속**(`IdentityBase`, tenant_id 없음) — 도움말은 제품이 제공하는 문구이고
회사 데이터가 아니다. `scoping_templates` 와 같은 자리다.

유니크는 처음부터 부분 유니크(`(key, locale) WHERE NOT is_deleted`) — 13.9-35 ④·13.9-42·
euc_iuc_inventory 와 같은 이유(소프트 삭제 행이 키를 점유하면 지웠다 다시 만들 수 없다).

**신규 테이블만 만든다. 기존 데이터를 바꾸지 않는다.** 문구 데이터는 이 마이그레이션이
넣지 않는다 — `python -m seeds.seed_help_texts` 가 넣는다(데이터 파일이 단일 원천).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def upgrade() -> None:
    op.create_table(
        'help_texts',
        sa.Column('key', sa.String(150), nullable=False),
        sa.Column('locale', sa.String(10), nullable=False),
        sa.Column('title', sa.String(300), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('source', sa.String(300), nullable=True),
        sa.Column('as_of', sa.Date(), nullable=True),
        sa.Column('baseline_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        *_identity_columns(),
    )
    op.create_index(
        'uq_help_texts_key_locale', 'help_texts', ['key', 'locale'],
        unique=True, postgresql_where=sa.text('NOT is_deleted'),
    )


def downgrade() -> None:
    op.drop_index('uq_help_texts_key_locale', table_name='help_texts')
    op.drop_table('help_texts')
