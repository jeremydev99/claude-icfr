"""baseline 테넌트 소유권 전환 + 격리 복합 FK (ADR-0030)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-01 00:00:00.000000+00:00

baseline_* 5테이블이 IdentityBase(전역 공유)였다. 운영 baseline 93건은 사이냅소프트
한 회사의 RCM인데 전역으로 정의돼 있었고, 테넌트가 1개뿐이라 드러나지 않았다.
code 유니크도 전역 단일 컬럼이라 **두 번째 테넌트가 온보딩되지 않는 상태**였다.

이 리비전이 하는 일:
1. baseline 5테이블에 tenant_id 추가 (nullable → 백필 → NOT NULL)
2. code 유니크 4개를 (tenant_id, code) 로 전환
3. baseline 4테이블에 (id, tenant_id) 유니크 — 복합 FK 의 참조 대상
4. instance→baseline FK 8개를 복합 FK 로 전환 (테넌트 격리를 DB 가 보장, §2.3)
5. **baseline 내부 FK 4개도 복합 FK 로 전환** — instance 경로만 막고 baseline 끼리의
   참조를 열어두면 "격리를 DB 가 구조적으로 보장한다"가 참이 아니다. A 사 하위프로세스가
   B 사 프로세스를 가리키는 조합이 남는다. 같은 종류의 구멍을 두 번에 나눠 막지 않는다.
6. baseline_control_assertions 유니크에 tenant_id 포함

baseline_risk_categories 는 전역 유지 — 제도가 정하는 고정 집합이며 회사가 바꿀 대상이
아니다(ADR-0029 §2.3, ADR-0030 §2.1). 이를 참조하는 FK 도 변경하지 않는다.

**FK 이름을 추정하지 않는다** — 기존 8개는 이름 없이 생성돼 DB 가 자동 명명했다.
inspector 로 실제 이름을 조회해 drop 한다(환경마다 다를 수 있다).

**테넌트가 정확히 1건이 아니면 중단한다.** 귀속 대상이 모호한 상태에서 실데이터를
특정 테넌트에 밀어넣지 않는다 — 수동 판단이 필요하다.

down 위험: downgrade 는 tenant_id 를 삭제하므로 **2번째 테넌트 데이터가 이미 들어온
뒤에는 code 전역 유니크 재생성이 실패한다.** 의도된 동작(정직한 down) — 롤백하려면
중복 데이터 정리가 선행돼야 한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# tenant_id 를 갖게 되는 baseline 테이블. risk_categories 는 제외(전역 유지).
BASELINE_TABLES = [
    'baseline_processes',
    'baseline_sub_processes',
    'baseline_risks',
    'baseline_controls',
    'baseline_control_assertions',
]

# code 유니크를 (tenant_id, code) 로 바꾸는 테이블 = 복합 FK 참조 대상이기도 하다.
CODED_TABLES = [
    'baseline_processes',
    'baseline_sub_processes',
    'baseline_risks',
    'baseline_controls',
]

# (instance 테이블, 컬럼, 대상 baseline 테이블, 새 제약명) — ADR-0030 §2.3 의 8개.
COMPOSITE_FKS = [
    ('process_instances', 'baseline_process_id', 'baseline_processes',
     'fk_process_instances_baseline_tenant'),
    ('sub_process_instances', 'baseline_sub_process_id', 'baseline_sub_processes',
     'fk_sub_process_instances_baseline_tenant'),
    ('sub_process_instances', 'process_baseline_id', 'baseline_processes',
     'fk_sub_process_instances_process_baseline_tenant'),
    ('risk_instances', 'baseline_risk_id', 'baseline_risks',
     'fk_risk_instances_baseline_tenant'),
    ('risk_instances', 'sub_process_baseline_id', 'baseline_sub_processes',
     'fk_risk_instances_sub_process_baseline_tenant'),
    ('control_instances', 'baseline_control_id', 'baseline_controls',
     'fk_control_instances_baseline_tenant'),
    ('control_instances', 'risk_baseline_id', 'baseline_risks',
     'fk_control_instances_risk_baseline_tenant'),
    ('control_assertion_instances', 'control_baseline_id', 'baseline_controls',
     'fk_control_assertion_instances_control_baseline_tenant'),
]

# baseline 내부 참조 4개 — 위 8개와 같은 방식으로 막는다 (§2.3 사각지대, 2026-09-01 추가).
# 주의: baseline_controls.risk_id 만 nullable 이다(나머지 3개는 NOT NULL). 그 컬럼이 NULL 인
# 행은 MATCH SIMPLE 상 검사 대상이 아니며, 이는 "상위 없는 통제"를 허용해온 기존 규약과 일치한다.
BASELINE_INTERNAL_FKS = [
    ('baseline_sub_processes', 'process_id', 'baseline_processes',
     'fk_baseline_sub_processes_process_tenant'),
    ('baseline_risks', 'sub_process_id', 'baseline_sub_processes',
     'fk_baseline_risks_sub_process_tenant'),
    ('baseline_controls', 'risk_id', 'baseline_risks',
     'fk_baseline_controls_risk_tenant'),
    ('baseline_control_assertions', 'baseline_control_id', 'baseline_controls',
     'fk_baseline_control_assertions_control_tenant'),
]

_ASSERTION_UQ = 'uq_baseline_control_assertions_control_category'


def _single_tenant_id(bind) -> str:
    """귀속 대상 테넌트 id. 정확히 1건이 아니면 중단 (ADR-0030 §2.5).

    id 를 하드코딩하지 않는다 — 환경마다 다를 수 있고, 무엇보다 '어느 회사의 표준인가'는
    데이터가 답해야 하는 질문이다.
    """
    rows = bind.execute(sa.text("SELECT id, code FROM tenants")).fetchall()
    if len(rows) != 1:
        raise RuntimeError(
            f"[중단] tenants 가 {len(rows)}건입니다(기대 1건). baseline 을 어느 회사에 귀속시킬지 "
            f"자동으로 정할 수 없습니다. 수동 판단 후 이 리비전을 조정하세요. 현재: "
            f"{[(str(r[0]), r[1]) for r in rows]}"
        )
    return rows[0][0]


def _find_fk_name(inspector, table: str, column: str, referred_table: str) -> str | None:
    """(컬럼 → 대상테이블) 단순 FK 의 실제 제약명. 없으면 None(이미 전환된 상태)."""
    for fk in inspector.get_foreign_keys(table):
        if fk['constrained_columns'] == [column] and fk['referred_table'] == referred_table:
            return fk['name']
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tenant_id = _single_tenant_id(bind)

    # ── 1~3. tenant_id 추가 → 백필 → NOT NULL ──────────────────────────
    for t in BASELINE_TABLES:
        op.add_column(t, sa.Column('tenant_id', PG_UUID(as_uuid=True), nullable=True))
        op.execute(sa.text(f"UPDATE {t} SET tenant_id = :tid").bindparams(tid=tenant_id))
        op.alter_column(t, 'tenant_id', nullable=False)
        op.create_index(f'ix_{t}_tenant_id', t, ['tenant_id'], unique=False)
        op.create_foreign_key(f'fk_{t}_tenant', t, 'tenants', ['tenant_id'], ['id'])

    # ── 4~5. code 유니크 전역 → (tenant_id, code) ──────────────────────
    for t in CODED_TABLES:
        op.drop_index(f'ix_{t}_code', table_name=t)          # UNIQUE 인덱스였다
        op.create_unique_constraint(f'uq_{t}_tenant_code', t, ['tenant_id', 'code'])
        op.create_index(f'ix_{t}_code', t, ['code'], unique=False)

    # ── 6. (id, tenant_id) 유니크 — 복합 FK 참조 대상 ───────────────────
    # id 는 이미 PK 라 유일하지만, FK 가 (id, tenant_id) 쌍을 참조하려면 그 조합에
    # 유니크 제약이 있어야 한다(postgres 요구사항).
    for t in CODED_TABLES:
        op.create_unique_constraint(f'uq_{t}_id_tenant', t, ['id', 'tenant_id'])

    # ── 7~8. instance→baseline + baseline 내부 FK 를 복합 FK 로 ────────
    # 반드시 6 이후여야 한다 — 참조 대상의 (id, tenant_id) 유니크가 먼저 있어야 한다.
    for table, column, target, name in COMPOSITE_FKS + BASELINE_INTERNAL_FKS:
        old = _find_fk_name(inspector, table, column, target)
        if old:
            op.drop_constraint(old, table, type_='foreignkey')
        op.create_foreign_key(
            name, table, target, [column, 'tenant_id'], ['id', 'tenant_id'],
        )

    # ── 9. 어서션 junction 유니크에 tenant_id 포함 ──────────────────────
    op.drop_constraint(_ASSERTION_UQ, 'baseline_control_assertions', type_='unique')
    op.create_unique_constraint(
        _ASSERTION_UQ, 'baseline_control_assertions',
        ['tenant_id', 'baseline_control_id', 'baseline_risk_category_id'],
    )


def downgrade() -> None:
    # 9 역순
    op.drop_constraint(_ASSERTION_UQ, 'baseline_control_assertions', type_='unique')
    op.create_unique_constraint(
        _ASSERTION_UQ, 'baseline_control_assertions',
        ['baseline_control_id', 'baseline_risk_category_id'],
    )

    # 8~7 역순 — 복합 FK 제거 후 단순 FK 복원(이름은 DB 자동 명명에 맡긴다).
    # baseline 내부 FK 를 먼저 되돌린다 — (id, tenant_id) 유니크 삭제보다 앞서야 한다.
    for table, column, target, name in BASELINE_INTERNAL_FKS + COMPOSITE_FKS:
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(None, table, target, [column], ['id'])

    # 6
    for t in CODED_TABLES:
        op.drop_constraint(f'uq_{t}_id_tenant', t, type_='unique')

    # 5~4 역순 — 전역 code 유니크 복원.
    # 2번째 테넌트가 이미 같은 code 를 쓰고 있으면 여기서 실패한다(정직한 down).
    for t in CODED_TABLES:
        op.drop_index(f'ix_{t}_code', table_name=t)
        op.drop_constraint(f'uq_{t}_tenant_code', t, type_='unique')
        op.create_index(f'ix_{t}_code', t, ['code'], unique=True)

    # 3~1 역순
    for t in BASELINE_TABLES:
        op.drop_constraint(f'fk_{t}_tenant', t, type_='foreignkey')
        op.drop_index(f'ix_{t}_tenant_id', table_name=t)
        op.drop_column(t, 'tenant_id')
