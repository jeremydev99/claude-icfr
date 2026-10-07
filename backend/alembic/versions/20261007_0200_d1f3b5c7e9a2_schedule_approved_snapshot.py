"""일정안 승인본 사본 — 추가만 (13.9-100)

Revision ID: d1f3b5c7e9a2
Revises: c9e1a3b5d7f0
Create Date: 2026-10-07 02:00:00

`schedule_plans.approved_items`(JSON)·`approved_version` 두 열. 화면은 마지막 승인본만 보고, 수정은 승인 때 반영한다.
이미 '승인' 상태인 일정안은 지금 항목을 승인본으로 채운다(그 상태가 곧 승인본이므로 의미는 같다). 운영은 일정안 0건.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd1f3b5c7e9a2'
down_revision: Union[str, None] = 'c9e1a3b5d7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedule_plans', sa.Column('approved_items', sa.JSON(), nullable=True))
    op.add_column('schedule_plans', sa.Column('approved_version', sa.Integer(), nullable=True))
    conn = op.get_bind()
    plans = conn.execute(sa.text(
        "SELECT id, version FROM schedule_plans WHERE status = 'approved' AND NOT is_deleted")).fetchall()
    for pid, ver in plans:
        rows = conn.execute(sa.text(
            "SELECT id, kind, template_code, title, category, start_date, end_date, description, tasks "
            "FROM schedule_items WHERE plan_id = :p AND NOT is_deleted ORDER BY start_date, sort_order"), {"p": pid}).fetchall()
        items = [{"id": str(r[0]), "kind": r[1], "template_code": r[2], "title": r[3], "category": r[4],
                  "start_date": r[5].isoformat(), "end_date": r[6].isoformat(), "description": r[7],
                  "tasks": (json.loads(r[8]) if isinstance(r[8], str) else r[8]) or []} for r in rows]
        conn.execute(sa.text("UPDATE schedule_plans SET approved_items = CAST(:j AS JSON), approved_version = :v WHERE id = :p"),
                     {"j": json.dumps(items, ensure_ascii=False), "v": ver, "p": pid})


def downgrade() -> None:
    op.drop_column('schedule_plans', 'approved_version')
    op.drop_column('schedule_plans', 'approved_items')
