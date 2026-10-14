"""증빙 문서명·비고 — evidence_files.title, evidence_files.note (13.9-122)

Revision ID: a7c9e1b3d5f6
Revises: f4b6d8a0c2e5
Create Date: 2026-10-13 02:00:00.000000+00:00

**추가만 한다 — 기존 데이터를 바꾸지 않는다.** nullable 컬럼 2개. 기존 증빙은 NULL(문서명은 파일명으로 대신 보인다).
운영평가 엑셀 내보내기(통제 1건 = 시트 1장)의 "문서명 | 비고" 칸을 채우는 값이다.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a7c9e1b3d5f6'
down_revision: str | None = 'f4b6d8a0c2e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('evidence_files', sa.Column('title', sa.String(200), nullable=True))
    op.add_column('evidence_files', sa.Column('note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('evidence_files', 'note')
    op.drop_column('evidence_files', 'title')
