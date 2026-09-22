"""Test 계열 5테이블 control_id 를 baseline/instance 두 컬럼으로 분리 (선택지 2)

Revision ID: 6b6d7fd94f0d
Revises: a9b0c1d2e3f4
Create Date: 2026-09-21 00:00:00.000000+00:00

**Test 계열 FK 가 옛 `controls.id` 를 가리키고 있었다.** RCM 통제 저장 경로가
`baseline_controls`/`control_instances` 로 옮겨가면서(ADR-0027) `POST /api/rcm/controls` 가 만든
통제 id 는 `controls` 에 없고, 그 id 로 RAWC·TestRun 을 만들면 FK 위반(409)이 난다.

**FK 하나로는 풀 수 없다.** 통제의 정체성 id 는 baseline 유래면 `baseline_controls.id`,
회사가 추가한 통제면 `control_instances.id` 라 두 테이블에 걸쳐 있다(13.9-27 과 같은 이유).
그래서 참조 컬럼을 둘로 나눈다.

- `baseline_control_id` → `baseline_controls(id, tenant_id)` **복합 FK**
  (기존 `fk_control_instances_baseline_tenant` 등과 같은 규약, 컬럼 순서 `(…_id, tenant_id)`)
- `instance_control_id` → `control_instances(id)` **단일 FK**
  (`control_assertion_instances.control_instance_id` 와 같은 규약. `control_instances` 에는
  `(id, tenant_id)` 유니크가 없어 복합으로 걸 수 없다 — 테넌트 일치는 DB 가 아니라 앱이 지킨다)
- CHECK: 둘 다 non-null 금지. **"정확히 하나"가 아니라 "둘 다 아님"** 이다 —
  `deficiencies.control_id` 는 원래 NULL 허용이고 실제로 NULL 2건이 있다.

**기존 `control_id` 는 지우지 않는다.** additive 이고 되돌리기 쉽다. NOT NULL 이던 4테이블은
nullable 로만 완화한다(신규 행이 새 컬럼만 채울 수 있도록). 컬럼 제거는 앱 코드 전환 후 별도 마이그레이션.

**백필**: 옛 `controls.code` = `baseline_controls.code`, 동일 tenant. 적용 전 실측(2026-09-21)으로
매핑 불가 행 0건 — control_risk_assessments 2 · test_runs 1 · control_assertions 469
(통제 93개 × 어서션) · deficiencies 2(+control_id NULL 2건은 그대로) · design_assessments 0.
`baseline_controls` 는 `(tenant_id, code)` 유니크라 한 행이 여러 baseline 에 매핑되지 않는다.

**UPDATE 는 쉼표 조인이어야 한다.** `FROM controls c JOIN baseline_controls b ON … x.tenant_id`
처럼 UPDATE 대상(`x`)을 JOIN … ON 에서 참조하면 PostgreSQL 이
`invalid reference to FROM-clause entry` 로 거부한다. tenant 조건을 WHERE 로 둔다.

**리비전 ID 재배치(2026-09-22)**: 최초 작성 시 ID `f8a9b0c1d2e3`·down_revision `e7f8a9b0c1d2`
로 로컬에서만 존재했으나, 같은 ID 로 별개 리비전(EUC·IUC 인벤토리)이 origin 에 먼저 병합되어
충돌했다. 로직 변경 없이 ID 를 `6b6d7fd94f0d`, down_revision 을 origin 병합 후 tip 인
`a9b0c1d2e3f4`(스코핑 코어) 로 재배치했다.

downgrade 주의: 백필된 baseline/instance 값은 **소실**된다. 또한 upgrade 이후 새 컬럼만 채워
`control_id` 가 NULL 인 행이 생기면 NOT NULL 복원이 실패한다(적용 시점 기준으로는 없다).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = '6b6d7fd94f0d'
down_revision: Union[str, None] = 'a9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    'control_risk_assessments',
    'test_runs',
    'control_assertions',
    'deficiencies',
    'design_assessments',
)
# control_id 가 NOT NULL 이던 테이블. deficiencies 는 원래 NULL 허용이라 제외.
_NOT_NULL_TABLES = tuple(t for t in _TABLES if t != 'deficiencies')

_CHECK_SQL = 'NOT (baseline_control_id IS NOT NULL AND instance_control_id IS NOT NULL)'


def _backfill_sql(table: str) -> str:
    return (
        f'UPDATE {table} AS x SET baseline_control_id = b.id '
        'FROM controls c, baseline_controls b '
        'WHERE x.control_id = c.id AND b.code = c.code AND b.tenant_id = x.tenant_id '
        'AND c.tenant_id = x.tenant_id'
    )


def upgrade() -> None:
    for t in _TABLES:
        op.add_column(t, sa.Column('baseline_control_id', PG_UUID(as_uuid=True), nullable=True))
        op.add_column(t, sa.Column('instance_control_id', PG_UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f'fk_{t}_baseline_control_tenant', t, 'baseline_controls',
            ['baseline_control_id', 'tenant_id'], ['id', 'tenant_id'],
        )
        op.create_foreign_key(
            f'fk_{t}_instance_control', t, 'control_instances',
            ['instance_control_id'], ['id'],
        )
        op.create_check_constraint(f'ck_{t}_ctrl_one', t, _CHECK_SQL)
        op.execute(_backfill_sql(t))

    for t in _NOT_NULL_TABLES:
        op.alter_column(t, 'control_id', existing_type=PG_UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    for t in reversed(_TABLES):
        op.drop_constraint(f'ck_{t}_ctrl_one', t, type_='check')
        op.drop_constraint(f'fk_{t}_instance_control', t, type_='foreignkey')
        op.drop_constraint(f'fk_{t}_baseline_control_tenant', t, type_='foreignkey')
        op.drop_column(t, 'instance_control_id')
        op.drop_column(t, 'baseline_control_id')

    for t in _NOT_NULL_TABLES:
        op.alter_column(t, 'control_id', existing_type=PG_UUID(as_uuid=True), nullable=False)
