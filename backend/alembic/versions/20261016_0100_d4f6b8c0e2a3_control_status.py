"""통제현황(WTT summary) 칸 — 원천 RCM 엑셀 AW열 (13.9-134, 조사 3)

Revision ID: d4f6b8c0e2a3
Revises: c3e5a7b9d1f2
Create Date: 2026-10-16 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.**
- `baseline_controls`·`control_instances`: `control_status`(text, nullable). 원천 엑셀 '통제현황(WTT의 summary 수준)'
  이며 그동안 업로드 때 버려졌다. 운영 값은 v4 원본 파일에서 1회 보강 적재한다(별도 스크립트, 재승인 없음 —
  `docs/investigation_control4.md` §3 결정).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd4f6b8c0e2a3'
down_revision: str | None = 'c3e5a7b9d1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ('baseline_controls', 'control_instances')


def upgrade() -> None:
    for t in _TABLES:
        op.add_column(t, sa.Column('control_status', sa.Text(), nullable=True))


def downgrade() -> None:
    for t in _TABLES:
        op.drop_column(t, 'control_status')
