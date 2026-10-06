"""통제 변경 결재 (2026-10-06, 마스터 지시) — 통제 편집은 바로 반영하지 않고 결재를 거친다.

흐름: 작성자 **임시저장**(draft) → **상신**(조직장: 통제책임자 주 소속 부서장, role_resolver 의 부서승인자)
→ 조직장 **승인**(dept_approved — 내부회계 대기함에 임시 보관) → 내부회계 담당자 **일괄 상신**(batch)
→ 내부회계관리자 **항목별 승인/반려** → 승인 항목만 RCM 에 반영(`_apply_control_update` — override 규약 그대로).
반려(조직장·관리자 어디서든)는 작성자에게 돌아간다(rejected → 고쳐서 다시 임시저장).

조직장이 없거나 작성자 본인이 조직장이면 조직장 단계를 건너뛰고 사유를 남긴다(`dept_skipped`).
통제 하나에 진행 중인 변경은 하나만 — 두 사람이 같은 통제를 동시에 고치면 승인 순서에 따라 서로 덮는다.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

ENTITY_CONTROL_CHANGE = "control_change"

CH_DRAFT = "draft"                # 임시저장
CH_DEPT_REVIEW = "dept_review"    # 조직장 결재 중
CH_DEPT_APPROVED = "dept_approved"  # 조직장 승인 — 내부회계 대기함
CH_IN_BATCH = "in_batch"          # 일괄 상신됨 — 내부회계관리자 결재 중
CH_APPLIED = "applied"            # 승인·반영
CH_REJECTED = "rejected"          # 반려 — 작성자가 고쳐 다시
CH_WITHDRAWN = "withdrawn"        # 작성자 회수
ACTIVE = (CH_DRAFT, CH_DEPT_REVIEW, CH_DEPT_APPROVED, CH_IN_BATCH, CH_REJECTED)
STATUS_LABELS = {CH_DRAFT: "임시저장", CH_DEPT_REVIEW: "조직장 결재 중", CH_DEPT_APPROVED: "내부회계 대기",
                 CH_IN_BATCH: "관리자 결재 중", CH_APPLIED: "반영 완료", CH_REJECTED: "반려", CH_WITHDRAWN: "회수"}

B_REVIEW, B_DONE = "review", "done"


class ControlChange(AuditedBase):
    __tablename__ = "control_changes"
    control_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    control_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    control_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)   # 필드 → 새 값
    before: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)    # 필드 → 상신 시점 값
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CH_DRAFT, index=True)
    author_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dept_approver_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    dept_skipped: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dept_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dept_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    admin_decided_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    admin_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(20), nullable=True)   # dept | admin


class ControlChangeBatch(AuditedBase):
    __tablename__ = "control_change_batches"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=B_REVIEW)
    submitted_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decided_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
