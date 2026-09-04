"""증빙 삭제 이력 컬럼 추가 (3-3, ADR-0032 §2.4)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-04 04:00:00.000000+00:00

**증빙은 감사 증거물이다. 지워지면 안 된다.**

수정 전 `DELETE /api/evidence/files/{id}` 는 `remove_object_safe` 로 **MinIO 파일을
실제 삭제**했다. 운영 실측(2026-09-04)에서 `is_deleted=true` 인 2건의 객체가 이미
사라져 있었다 — 테스트 파일이라 손실은 없었으나 동작이 그대로면 실증빙에서 같은
일이 난다. 버킷 전체 객체는 `test2.pdf` 12바이트 1건뿐이었다.

`AuditedBase` 의 `deleted_at`/`deleted_by` 는 문자열 컬럼이라 "누가"를 계정으로
되짚을 수 없다. 증빙은 **"누가 언제 올렸다가 지웠는지"가 감사에서 실제로 묻는
질문**이므로 계정 FK 로 따로 남긴다.

컬럼명이 `deleted_at_ts` 인 것은 `SoftDeleteMixin.deleted_at`(문자열 계열 감사 컬럼)과
이름이 충돌하기 때문이다. 기존 컬럼을 바꾸면 전 테이블에 영향이 가므로 새 이름을 쓴다.

기존 4건은 건드리지 않는다 — 시드·테스트 잔재이며 실데이터 조작을 하지 않는다
(`ClaudeICFR.md` 13.9 참조).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('evidence_files', sa.Column(
        'deleted_by_id', PG_UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('evidence_files', sa.Column(
        'deleted_at_ts', sa.DateTime(timezone=True), nullable=True))
    op.add_column('evidence_files', sa.Column('delete_reason', sa.Text(), nullable=True))
    op.create_index('ix_evidence_files_deleted_by_id', 'evidence_files', ['deleted_by_id'])


def downgrade() -> None:
    op.drop_index('ix_evidence_files_deleted_by_id', table_name='evidence_files')
    op.drop_column('evidence_files', 'delete_reason')
    op.drop_column('evidence_files', 'deleted_at_ts')
    op.drop_column('evidence_files', 'deleted_by_id')
