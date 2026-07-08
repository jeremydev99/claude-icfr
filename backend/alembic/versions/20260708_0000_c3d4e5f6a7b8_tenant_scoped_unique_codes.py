"""tenant-scoped unique codes: 글로벌 unique(code) → (tenant_id, code) 복합 unique 전환 (ADR-0026)

Revision ID: c3d4e5f6a7b8
Revises: b1f2c3d4e5a6
Create Date: 2026-07-08 00:00:00.000000+00:00

2번째 tenant 진입 시 서로 다른 회사가 같은 code를 쓰지 못하던 제약을 해소한다.
대상: controls, deficiencies, processes, risk_categories, risks, sub_processes.
users.email 은 제외 — 전역 계정(ADR-0025)이라 tenant 비종속 유지.

down 위험: 2번째 tenant 데이터가 이미 들어와 code가 tenant 간 중복된 상태에서는
downgrade의 글로벌 unique 인덱스 재생성이 실패한다. 이는 의도된 동작(정직한 down) —
롤백이 필요하면 중복 데이터 정리가 선행돼야 한다.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b1f2c3d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ['controls', 'deficiencies', 'processes', 'risk_categories', 'risks', 'sub_processes']


def upgrade() -> None:
    for t in TABLES:
        op.drop_index(f'ix_{t}_code', table_name=t)
        op.create_unique_constraint(f'uq_{t}_tenant_code', t, ['tenant_id', 'code'])
        op.create_index(f'ix_{t}_code', t, ['code'], unique=False)


def downgrade() -> None:
    for t in TABLES:
        op.drop_index(f'ix_{t}_code', table_name=t)
        op.drop_constraint(f'uq_{t}_tenant_code', t, type_='unique')
        op.create_index(f'ix_{t}_code', t, ['code'], unique=True)
