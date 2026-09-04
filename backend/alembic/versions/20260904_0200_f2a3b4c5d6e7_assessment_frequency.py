"""통제 평가주기 컬럼 추가 (3-2, ADR-0032 §2.1)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-04 02:00:00.000000+00:00

**평가주기는 통제 수행 주기(`frequency`)와 다른 개념이다.**
`frequency` 는 "통제를 얼마나 자주 수행하는가"(O/D/W/M/Q/A), 이쪽은 "얼마나 자주
평가하는가"다. 원천 엑셀에도 6행 `통제주기`(col 35)와 7행 `평가주기`(col 55)로
**별도 열**이 존재한다.

**백필값은 판단이 아니라 원천 데이터다.** 엑셀 `평가주기` 열 실측 결과
A 91 / Q 1 / M 1 이므로, 기본값 `annual` 로 채우고 예외 2건만 code 로 지정한다.

    FA-040-10-10   평가주기 Q → quarterly   (통제주기는 A)
    FR-040-10-10   평가주기 M → monthly     (통제주기는 Q)

엑셀을 읽는 마이그레이션은 만들지 않았다 — 파일 의존이 생기고 파일이 없는 환경에서
실패한다. 파서(`_parse_rcm_sheet`)가 col 55 를 읽게 하는 확장은 별건이다.
**reseed 로 백필하는 경로는 쓸 수 없다** — `role_assignments.target_id` 가 baseline id 를
FK 없이 가리키므로(정체성 id 규칙) 재시딩하면 배정이 조용히 끊어진다.

일 단위(D)·수시(O)는 평가주기 값 집합에 없다(ADR-0032 §2.1). 실측에서도 등장하지 않아
매핑 충돌이 없다.

`control_instances.assessment_frequency` 는 nullable override — NULL 이면 baseline 을
따른다(2-A-4-1 미러링 규약).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 원천 엑셀 `평가주기` 열에서 annual 이 아닌 것 (실측 2건)
_EXCEPTIONS = {
    'FA-040-10-10': 'quarterly',
    'FR-040-10-10': 'monthly',
}


def upgrade() -> None:
    op.add_column('baseline_controls', sa.Column(
        'assessment_frequency', sa.String(12), nullable=False, server_default='annual'))
    op.add_column('control_instances', sa.Column(
        'assessment_frequency', sa.String(12), nullable=True))

    for code, value in _EXCEPTIONS.items():
        op.execute(
            sa.text("UPDATE baseline_controls SET assessment_frequency = :v WHERE code = :c")
            .bindparams(v=value, c=code)
        )

    # server_default 는 백필용이었다 — 이후 삽입은 모델 기본값(ORM)이 채운다.
    # 남겨두면 스키마에 기본값이 두 벌(DB + ORM)이 되어 무엇이 진실인지 갈린다.
    op.alter_column('baseline_controls', 'assessment_frequency', server_default=None)


def downgrade() -> None:
    op.drop_column('control_instances', 'assessment_frequency')
    op.drop_column('baseline_controls', 'assessment_frequency')
