"""증빙 통제×회차 부착 컬럼 추가 (3-3, ADR-0032 §2.7)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-08 00:00:00.000000+00:00

**증빙은 통제 × 회차에 붙는다.** 같은 통제라도 회차가 다르면 다른 증빙이다.

활동(`assessment_activities`)이 아니라 통제×회차에 직접 붙인 이유:
① 활동은 같은 통제·회차에 여러 번 남을 수 있어(재수행·보완) 활동에 붙이면
   "어느 수행분의 증빙인가"가 갈린다
② 마감 미완 판정이 통제×회차 단위라 증빙도 같은 축이어야 짝이 맞는다
③ §2.2 경로가 `cycles/{cycle_id}/controls/{control_id}` 구조다

**nullable 로 둔다.** 기존 4건(시드·테스트 잔재)이 있고 그 데이터를 조작하지
않기로 확정했다(13.9-29). NOT NULL 로 만들면 4건을 지우거나 값을 지어내야 한다.
**신규 업로드는 핸들러가 필수로 막는다** — "레거시는 NULL 을 허용하되 신규는
만들지 않는다"를 애플리케이션이 담당한다.

`cycle_id` 에도 FK 를 걸지 않는다. 걸 수는 있으나(`assessment_cycles` 는 단일 테이블)
`control_id` 가 정체성 id 규칙상 FK 를 걸 수 없어(baseline/instance 두 테이블) 한쪽만
FK 이면 "이 두 컬럼이 짝"이라는 사실이 스키마에서 흐려진다. 둘 다 핸들러가 검증한다.

기존 4건은 `cycle_id`/`control_id` 가 NULL 인 레거시 증빙으로 남는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evidence_files', sa.Column('cycle_id', PG_UUID(as_uuid=True), nullable=True))
    op.add_column('evidence_files', sa.Column('control_id', PG_UUID(as_uuid=True), nullable=True))
    op.create_index('ix_evidence_files_cycle_id', 'evidence_files', ['cycle_id'])
    op.create_index('ix_evidence_files_control_id', 'evidence_files', ['control_id'])


def downgrade() -> None:
    op.drop_index('ix_evidence_files_control_id', table_name='evidence_files')
    op.drop_index('ix_evidence_files_cycle_id', table_name='evidence_files')
    op.drop_column('evidence_files', 'control_id')
    op.drop_column('evidence_files', 'cycle_id')
