"""Test 계열 5테이블 control_id 를 baseline/instance 두 컬럼으로 분리 (선택지 2)

Revision ID: 6b6d7fd94f0d
Revises: f5a6b7c8d9e0
Create Date: 2026-09-21 00:00:00.000000+00:00

**Test 계열 FK 가 옛 `controls.id` 를 가리키고 있었다.** RCM 통제 저장 경로가
`baseline_controls`/`control_instances` 로 옮겨가면서(ADR-0027) `POST /api/rcm/controls` 가 만든
통제 id 는 `controls` 에 없고, 그 id 로 RAWC·TestRun 을 만들면 FK 위반(409)이 난다.

**FK 하나로는 풀 수 없다.** 통제의 정체성 id 는 baseline 유래면 `baseline_controls.id`,
회사가 추가한 통제면 `control_instances.id` 라 두 테이블에 걸쳐 있다(13.9-27 과 같은 이유).
그래서 참조 컬럼을 둘로 나눈다.

- `baseline_control_id` → 논리적으로 `baseline_controls(id, tenant_id)`
- `instance_control_id` → 논리적으로 `control_instances(id)`
- CHECK: 둘 다 non-null 금지. **"정확히 하나"가 아니라 "둘 다 아님"** 이다 —
  `deficiencies.control_id` 는 원래 NULL 허용이고 실제로 NULL 2건이 있다.

**FK 없음(2026-09-22, FK-less 재작업) — 의도적.** 처음엔 위 두 참조에 DB FK(복합+단일)를
걸었으나, 코드베이스 지배 관례(evidence·assessment·euc/iuc 등, 13.9-27)는 "통제 정체성 id 는
baseline/instance 두 테이블에 걸쳐 있어 FK 하나로 못 거니 FK 를 안 걸고 핸들러가
`resolve_controls()` 로 존재를 검증한다"이다. 이 리비전만 FK 를 걸어 예외가 되고 있었다 —
FK 2개(복합 baseline, 단일 instance)와 그 downgrade 대응 drop 을 제거해 관례에 맞췄다.
**⚠️ 무결성 공백**: FK 제거 후 앱 코드가 resolver 검증을 붙이기 전까지는 두 컬럼에 임의 uuid 가
들어가도 DB 가 막지 못한다. 뒤따르는 모델/서비스 전환 프롬프트에서 즉시 닫아야 한다.

**기존 `control_id` 는 지우지 않는다.** additive 이고 되돌리기 쉽다. NOT NULL 이던 4테이블은
nullable 로만 완화한다(신규 행이 새 컬럼만 채울 수 있도록). 컬럼 제거는 앱 코드 전환 후 별도 마이그레이션.

**백필**: 옛 `controls.code` = `baseline_controls.code`, 동일 tenant. 적용 전 실측(2026-09-21)으로
매핑 불가 행 0건 — control_risk_assessments 2 · test_runs 1 · control_assertions 469
(통제 93개 × 어서션) · deficiencies 2(+control_id NULL 2건은 그대로) · design_assessments 0.
`baseline_controls` 는 `(tenant_id, code)` 유니크라 한 행이 여러 baseline 에 매핑되지 않는다.

**UPDATE 는 쉼표 조인이어야 한다.** `FROM controls c JOIN baseline_controls b ON … x.tenant_id`
처럼 UPDATE 대상(`x`)을 JOIN … ON 에서 참조하면 PostgreSQL 이
`invalid reference to FROM-clause entry` 로 거부한다. tenant 조건을 WHERE 로 둔다.

**리비전 ID 재배치(2026-09-22, 1차)**: 최초 작성 시 ID `f8a9b0c1d2e3`·down_revision `e7f8a9b0c1d2`
로 로컬에서만 존재했으나, 같은 ID 로 별개 리비전(EUC·IUC 인벤토리)이 origin 에 먼저 병합되어
충돌했다. 로직 변경 없이 ID 를 `6b6d7fd94f0d`, down_revision 을 origin 병합 후 tip 인
`a9b0c1d2e3f4`(스코핑 코어) 로 재배치했다.

**부모 재배치(2026-09-22, 2차)**: `a9b0c1d2e3f4` 아래 origin 에 `b1c2d3e4f5a6`(6-1b 스코핑 보완)
이 형제로 병합되어 alembic branch(head 2개) 상황이 됐다. revision ID(`6b6d7fd94f0d`)는 유지,
down_revision 만 `a9b0c1d2e3f4` → `b1c2d3e4f5a6` 로 재배치해 단일 head 로 정리. 로직 무변경.

**부모 재배치(2026-10-01, 3차, MERGE-02)**: `b1c2d3e4f5a6` 아래 origin 에 `c2d3e4f5a6b7`(7-A)부터
`f5a6b7c8d9e0`(8-E)까지 4건이 같은 부모로 병합되어 다시 head 2개가 됐다. revision ID 유지,
down_revision 만 `b1c2d3e4f5a6` → `f5a6b7c8d9e0` 로 재배치해 단일 head 로 정리. 로직 무변경.
로컬 DB 에 이미 적용돼 있던 터라 `alembic downgrade b1c2d3e4f5a6` 로 되돌린 뒤 재적용했다
(`ICFR-PROMPT-MERGE-02-alembic-relinear.md`).

downgrade 주의: 백필된 baseline/instance 값은 **소실**된다. 또한 upgrade 이후 새 컬럼만 채워
`control_id` 가 NULL 인 행이 생기면 NOT NULL 복원이 실패한다(적용 시점 기준으로는 없다).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = '6b6d7fd94f0d'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
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
        op.create_check_constraint(f'ck_{t}_ctrl_one', t, _CHECK_SQL)
        op.execute(_backfill_sql(t))

    for t in _NOT_NULL_TABLES:
        op.alter_column(t, 'control_id', existing_type=PG_UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    for t in reversed(_TABLES):
        op.drop_constraint(f'ck_{t}_ctrl_one', t, type_='check')
        op.drop_column(t, 'instance_control_id')
        op.drop_column(t, 'baseline_control_id')

    for t in _NOT_NULL_TABLES:
        op.alter_column(t, 'control_id', existing_type=PG_UUID(as_uuid=True), nullable=False)
