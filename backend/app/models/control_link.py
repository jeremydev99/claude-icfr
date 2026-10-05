"""통제 ↔ 계정 연결 (ADR-0040) — RCM 통제가 어느 계정을 다루는지 **구조화된 연결**로 남긴다.

RCM 의 `related_accounts` 는 자유 텍스트라 커버리지를 이름으로 추정해 왔다(13.9-78). 이 표가 생기면
**승인된 연결(active)이 있는 계정은 확정**, 없는 계정만 추정으로 보여 준다.

- 계정 = 회사 계정 체계(`fs_accounts`, 연도를 넘어 유지) — 스코핑 계정이 `fs_account_id` 로 가리킨다.
  주석(NOTE) 계정은 재무제표 계정이 없어 정규화한 이름 키(`note_key`)로 잇는다.
- `account_key` = fs_account_id 문자열 또는 `note:<정규화 이름>` — 한 통제·한 계정에 한 줄(부분 유니크).
- 통제 = resolver 정체성 id(baseline 유래면 baseline id, add 면 instance id). 코드·이름은 당시 표기를 남긴다.

상태(`state`):
- `draft`    — 작성 중 추가(자동 매칭 또는 실무자 드래그). 효력 없음
- `review`   — 검토 요청에 묶임(`proposal_id`). 잠김
- `active`   — 책임 1차·마스터 2차 승인 완료. 커버리지 확정 근거
- `dismissed`— 자동 매칭 결과를 사람이 뺐거나 반려됨. 자동 매칭이 다시 넣지 않는다

활성 연결의 해제는 `remove_state`(draft → review)로 같은 결재를 거친다. 승인되면 행을 지운다(soft delete).
"""
from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

ENTITY_CONTROL_LINK = "control_link"

L_DRAFT = "draft"
L_REVIEW = "review"
L_ACTIVE = "active"
L_DISMISSED = "dismissed"

SRC_AUTO = "auto"
SRC_MANUAL = "manual"


class ControlAccountLink(AuditedBase):
    __tablename__ = "control_account_links"
    __table_args__ = (
        ForeignKeyConstraint(["fs_account_id", "tenant_id"], ["fs_accounts.id", "fs_accounts.tenant_id"],
                             name="fk_control_account_links_fs_account_tenant"),
        Index("uq_control_account_links_key", "tenant_id", "control_id", "account_key", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    control_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    control_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    control_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fs_account_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    note_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_key: Mapped[str] = mapped_column(String(220), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=L_DRAFT)
    remove_state: Mapped[str | None] = mapped_column(String(20), nullable=True)   # None | draft | review
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=SRC_MANUAL)
    match_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)      # exact | partial | parent | alias
    match_token: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proposal_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
