"""이번 판 수정자 — approval_states.editor_ids (13.9-127)

Revision ID: b8d0f2a4c6e8
Revises: a7c9e1b3d5f6
Create Date: 2026-10-14 01:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** nullable JSON 칸 1개(사용자 id 문자열 목록). 기존 행은 NULL = 기록 전 판(수정자 없음으로 본다).
회계연도 RCM 이 작성 중일 때 RCM 을 바로 반영한 사람·변경 결재 신청자를 모으고, 그 사람은 그 판을 승인할 수 없다.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'b8d0f2a4c6e8'
down_revision: str | None = 'a7c9e1b3d5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('approval_states', sa.Column('editor_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('approval_states', 'editor_ids')
