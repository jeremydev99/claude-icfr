"""departments·user_departments 유니크를 살아 있는 행 한정으로 (4-2)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-19 00:00:00.000000+00:00

**소프트 삭제된 행이 이름·짝을 계속 점유해 재생성이 막혀 있었다.** 실측(2026-09-19):

    부서 "A" 생성 → 삭제 → 같은 이름 재생성      → 409 데이터 무결성 제약 위반
    소속 추가 → 제거 → 같은 부서에 다시 추가      → 409
    주 소속 지정 → 제거 → 다른 부서 주 소속 지정  → 409

셋 다 같은 원인이고, `uq_user_roles_active_pair`(13.9-35 ④)에서 이미 한 번 겪은 것이다.
409 문구도 앱 메시지가 아니라 IntegrityError 일반 문구라 **사용자는 원인을 알 수 없었다** —
"오타로 만든 부서를 지우고 다시 만들기"가 막히는데 이유가 화면에 나오지 않는다.

세 인덱스를 한 번에 바꾼다. **스키마 변경은 횟수 자체가 위험이므로** 같은 원인을 나눠서
올리지 않는다.

- `uq_departments_tenant_name`   제약 → 부분 유니크 인덱스 (NOT is_deleted)
- `uq_user_departments_pair`     제약 → 부분 유니크 인덱스 (NOT is_deleted)
- `uq_user_departments_one_primary` 부분 인덱스 조건에 `NOT is_deleted` 추가

`uq_departments_id_tenant`(복합 FK 참조 대상, ADR-0030 §2.3)는 **건드리지 않는다** —
그건 소프트 삭제와 무관하고 하위 테이블이 참조한다.

적용 전 중복 확인(운영). 살아 있는 행끼리 중복이 있으면 인덱스 생성이 실패한다:

    SELECT tenant_id, name, count(*) FROM departments
     WHERE NOT is_deleted GROUP BY 1,2 HAVING count(*) > 1;
    SELECT tenant_id, user_id, department_id, count(*) FROM user_departments
     WHERE NOT is_deleted GROUP BY 1,2,3 HAVING count(*) > 1;
    SELECT tenant_id, user_id, count(*) FROM user_departments
     WHERE is_primary AND NOT is_deleted GROUP BY 1,2 HAVING count(*) > 1;

로컬은 0건 확인(2026-09-19, departments 0행·user_departments 0행). 운영 확인은 마스터가 실행한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_departments_tenant_name', 'departments', type_='unique')
    op.create_index(
        'uq_departments_tenant_name', 'departments', ['tenant_id', 'name'],
        unique=True, postgresql_where=sa.text('NOT is_deleted'),
    )

    op.drop_constraint('uq_user_departments_pair', 'user_departments', type_='unique')
    op.create_index(
        'uq_user_departments_pair', 'user_departments',
        ['tenant_id', 'user_id', 'department_id'],
        unique=True, postgresql_where=sa.text('NOT is_deleted'),
    )

    op.drop_index('uq_user_departments_one_primary', table_name='user_departments')
    op.create_index(
        'uq_user_departments_one_primary', 'user_departments', ['tenant_id', 'user_id'],
        unique=True, postgresql_where=sa.text('is_primary AND NOT is_deleted'),
    )


def downgrade() -> None:
    op.drop_index('uq_user_departments_one_primary', table_name='user_departments')
    op.create_index(
        'uq_user_departments_one_primary', 'user_departments', ['tenant_id', 'user_id'],
        unique=True, postgresql_where=sa.text('is_primary'),
    )

    op.drop_index('uq_user_departments_pair', table_name='user_departments')
    op.create_unique_constraint(
        'uq_user_departments_pair', 'user_departments',
        ['tenant_id', 'user_id', 'department_id'],
    )

    op.drop_index('uq_departments_tenant_name', table_name='departments')
    op.create_unique_constraint('uq_departments_tenant_name', 'departments', ['tenant_id', 'name'])
