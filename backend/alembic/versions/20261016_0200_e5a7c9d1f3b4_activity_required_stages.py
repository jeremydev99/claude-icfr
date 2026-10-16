"""제출 시점 승인 단계 고정 — assessment_activities.required_stages (13.9-141)

Revision ID: e5a7c9d1f3b4
Revises: d4f6b8c0e2a3
Create Date: 2026-10-16 02:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.**
- `assessment_activities.required_stages`(varchar(30), nullable): 제출할 때 필요했던 승인 단계(콤마 구분, 예 `dept,assessor`).
  그동안은 매번 **현재** 역할로 다시 계산해, 회차 중 부서장이 바뀌면 이미 승인이 끝난 기록이 승인 대기로 돌아갔다.
  기존 행은 NULL = 종전대로 현재 역할로 계산(운영 제출 0건).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'e5a7c9d1f3b4'
down_revision: str | None = 'd4f6b8c0e2a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('assessment_activities', sa.Column('required_stages', sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column('assessment_activities', 'required_stages')
