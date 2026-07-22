"""baseline_version 컬럼 5테이블 추가 (ADR-0027, 2-B-3.5)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-16 03:00:00.000000+00:00

baseline 5테이블(processes/sub_processes/risks/risk_categories/controls)에
baseline 콘텐츠 개정 회차를 추적할 baseline_version(Integer, default=1, NOT NULL)만 추가.
개정 트랙에서 마이그레이션 + 전 tenant 백필 + 소급 매핑이 붙기 전에 컬럼 하나로 선반영
("지금은 컬럼 하나, 나중은 프로젝트 하나"). instance·기존 테이블 미변경.

- 기존 행은 server_default='1' 로 backfill 후 server_default 제거
  (모델은 app-side default=1 만 사용 — DB default 미보유 상태로 일치).
- VersionMixin.row_version(낙관적 잠금)과 다른 개념. 이름 충돌 없음.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = [
    'baseline_processes',
    'baseline_sub_processes',
    'baseline_risks',
    'baseline_risk_categories',
    'baseline_controls',
]


def upgrade() -> None:
    for table in _TABLES:
        # 기존 행 backfill=1 을 위해 server_default 로 추가 후 default 제거
        op.add_column(
            table,
            sa.Column('baseline_version', sa.Integer(), nullable=False, server_default='1'),
        )
        op.alter_column(table, 'baseline_version', server_default=None)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, 'baseline_version')
