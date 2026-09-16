"""user_roles 활성 행 부분 유니크 (13.9-35 ④, ADR-0031 §3.3)

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-16 00:00:00.000000+00:00

**같은 사용자·역할이 2행 저장될 수 있었다.** 1행을 지워도 역할이 남으므로
"해제했는데 권한이 유지되는" 상태가 된다. 앱에서 409 로 먼저 막지만(`api/user_mgmt.py`)
판별은 구조로 둔다 — 한 경로만 빠뜨려도 뚫리는 것이 13.9-35 의 원인이었다.

**부분 유니크여야 한다.** `user_roles` 는 소프트 삭제(`AuditedBase`)라
평범한 유니크 제약이면 **역할 해제 후 재배정이 IntegrityError 로 터진다** —
해제된 행이 그대로 남아 있기 때문이다. 재배정은 정상 업무이므로 살아 있는 행
(`NOT is_deleted`)만 대상으로 한다. 선례: `uq_user_departments_one_primary`
(`20260904_0000_d0e1f2a3b4c5`).

`tenant_id` 를 선두에 둔다 — 테넌트를 넘는 중복은 중복이 아니다(ADR-0030 격리).

**적용 전 중복 확인이 필요하다.** 중복이 있으면 인덱스 생성이 실패한다.
로컬은 0건으로 확인했고(2026-09-16, 총 3행 전부 구 역할명), 운영 확인·정리는
마스터가 직접 실행한다.

    SELECT tenant_id, user_id, role_name, count(*) FROM user_roles
     WHERE is_deleted = false GROUP BY 1,2,3 HAVING count(*) > 1;
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_user_roles_active_pair', 'user_roles',
        ['tenant_id', 'user_id', 'role_name'],
        unique=True, postgresql_where=sa.text('NOT is_deleted'),
    )


def downgrade() -> None:
    op.drop_index('uq_user_roles_active_pair', table_name='user_roles')
