"""검토·승인 거버넌스 저장소 (ADR-0038).

- `GovernanceEvent` — **지울 수 없는 이력**. 확인·확인 취소·값 변경·검토 요청·검토·승인·재오픈을 전·후 값과 함께 쌓는다.
  수정·삭제 API 가 없고, PostgreSQL 트리거가 UPDATE·DELETE 를 거부한다(마이그레이션 `9b2c4d6e8f10`).
- `ReopenRequest` — 확정 문서의 재오픈 요청과 그 결정(승인·거절).
- `ExternalApproval` / `GovernanceFile` — 마스터관리자 작성 문서의 **외부 승인 기록**(대표이사·이사회)과 증빙 스캔.

문서 식별은 `entity_type` + `entity_id` 다(1단계는 `scoping` 만). 2단계에서 RCM·평가·미비점·재무제표가 같은 표를 쓴다.
- `ApprovalState` — 스코핑 외 문서의 결재 상태(2-1). 스코핑은 자기 표의 칸을 그대로 쓴다.
"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy import false as sa_false
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

ENTITY_SCOPING = "scoping"

# 이벤트 종류 — 화면 표기(라벨)는 프론트가 가진다
EV_ITEM_CONFIRM = "item_confirm"
EV_ITEM_UNCONFIRM = "item_unconfirm"
EV_VALUE_CHANGE = "value_change"
EV_SUBMIT = "submit_review"
EV_WITHDRAW = "withdraw"
EV_REVIEW_DONE = "review_done"
EV_REVIEW_RETURN = "review_return"
EV_APPROVE = "approve"
EV_EXTERNAL_APPROVE = "external_approve"
EV_REOPEN_REQUEST = "reopen_request"
EV_REOPEN_APPROVE = "reopen_approve"
EV_REOPEN_REJECT = "reopen_reject"

# 승인 경로 (ADR-0038 §2.2) — 검토 요청 시점에 정해 저장한다
PATH_LEAD_THEN_MASTER = "lead_then_master"   # 일반관리자 작성 + 책임관리자 있음
PATH_MASTER = "master"                       # 책임관리자 작성, 또는 일반관리자 작성인데 책임관리자 0명
PATH_EXTERNAL = "external"                   # 마스터관리자 작성 → 대표이사·이사회

REOPEN_PENDING, REOPEN_APPROVED, REOPEN_REJECTED = "pending", "approved", "rejected"
EXTERNAL_BODIES = {"ceo": "대표이사", "board": "이사회"}


class GovernanceEvent(AuditedBase):
    __tablename__ = "governance_events"
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    # 바뀐 대상의 사람이 읽는 이름 — "계정 매출채권 · 질적 1" 같은 것. 대상 행이 지워져도 남는다
    target: Mapped[str | None] = mapped_column(String(300), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 문서 버전(재오픈마다 +1)


class ReopenRequest(AuditedBase):
    __tablename__ = "reopen_requests"
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    requested_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requested_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=REOPEN_PENDING)
    decided_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalApproval(AuditedBase):
    """대표이사·이사회 승인 기록 — 승인 행위가 아니라 **이미 일어난 외부 승인의 기록**이다(ADR-0038 §2.2.1)."""
    __tablename__ = "external_approvals"
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)          # approve | reopen
    reopen_request_id: Mapped[UUID | None] = mapped_column(ForeignKey("reopen_requests.id"), nullable=True)
    approver_body: Mapped[str] = mapped_column(String(20), nullable=False)    # ceo | board
    approved_on: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)  # "제5차 이사회" 등
    recorded_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


class GovernanceFile(AuditedBase):
    """외부 승인 증빙 파일(의사록·결재 문서 스캔). 본체는 MinIO, 경로는 `minio_client.build_governance_key`."""
    __tablename__ = "governance_files"
    external_approval_id: Mapped[UUID] = mapped_column(ForeignKey("external_approvals.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    minio_key: Mapped[str] = mapped_column(String(500), nullable=False)


ENTITY_FS_STATEMENT = "fs_statement"
ENTITY_DEFICIENCY = "deficiency"
ENTITY_ASSESSMENT_CYCLE = "assessment_cycle"
ENTITY_RCM_YEAR = "rcm_fiscal_year"
EV_CYCLE_CLOSE = "cycle_close"   # 평가 회차 마감(ADR-0038 2-4)

# 결재 상태(공통) — 스코핑의 STATUS_* 와 같은 값이라 `approval.can` 이 두 문서를 같은 규칙으로 판정한다
AS_DRAFT, AS_REVIEW, AS_CONFIRMED = "draft", "review", "confirmed"


class ApprovalState(AuditedBase):
    """문서 1건의 **결재 상태** (ADR-0038 2-1) — 스코핑 외 문서(재무제표·미비점·평가 결론·RCM)가 공통으로 쓴다.

    스코핑은 1단계에서 자기 표(`scopings`)에 같은 칸을 두었으므로 옮기지 않는다(데이터 이관 없음, 2026-10-07 결정).
    칸 이름을 스코핑과 같게 둔 것은 `approval.can` 이 둘을 구분하지 않고 판정하게 하려는 것이다.

    - 행이 없는 문서 = 아직 결재선을 탄 적 없음. 확정돼 있는데 행이 없으면 **2단계 이전 방식 확정**(ADR-0038 §3.1 Q3).
    - `legacy_confirmed` — 이전 방식 확정분에 재오픈 요청이 들어와 행을 처음 만들 때 True. 이력 표시용.
    """
    __tablename__ = "approval_states"
    __table_args__ = (
        # 문서 1건에 결재 상태 1행 — 처음부터 부분 유니크(13.9-35 ④·13.9-42 를 반복하지 않는다)
        Index("uq_approval_states_entity", "tenant_id", "entity_type", "entity_id", unique=True,
              sqlite_where=text("is_deleted = 0"), postgresql_where=text("NOT is_deleted")),
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AS_DRAFT)
    review_requested_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    review_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_path: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewed_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    legacy_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_false())
