"""제안 결재 — AI(또는 시스템) 초안 → 책임관리자 1차 승인(항목별) → 마스터관리자 2차 승인 → 반영 (ADR-0038 확장).

첫 용도는 **재무제표 계정 ↔ 스코핑 템플릿 계정 연결 제안**(`kind = fs_template_link`). 제안 자체는 효력이 없고,
2차 승인 순간에만 실제 링크(`fs_template_links`)가 만들어진다. 같은 틀을 다른 제안(RCM 표기 정정 등)에도 쓴다.

- 제안자: 행위자 문자열(`proposed_by`, 예 `system:claude-proposal`) — 사람이 아니면 시스템 행위자다(ADR-0036).
- 1차(책임관리자): 항목마다 승인·반려·변경 → 전 항목 결정 후 "검토 완료". 2차(마스터): 1차 검토자와 달라야 한다.
- 반려(1차·2차 어디서든)하면 묶음이 닫힌다(`returned`). 고친 제안은 새 묶음으로 낸다.
- 이력은 `governance_events`(entity_type = `proposal`).
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

ENTITY_PROPOSAL = "proposal"
KIND_FS_TEMPLATE_LINK = "fs_template_link"

P_PENDING_REVIEW = "pending_review"   # 1차 대기
P_REVIEWED = "reviewed"               # 1차 완료 → 2차 대기
P_APPROVED = "approved"               # 2차 승인·반영 완료
P_RETURNED = "returned"               # 반려(닫힘)
P_STATUS_LABELS = {P_PENDING_REVIEW: "1차 승인 대기", P_REVIEWED: "2차 승인 대기", P_APPROVED: "승인·반영 완료",
                   P_RETURNED: "반려"}

ITEM_LINK = "link"        # 템플릿 계정에 연결
ITEM_MANUAL = "manual"    # 대응 템플릿 없음 — 직접 평가 권고
D_PENDING, D_ACCEPTED, D_REJECTED, D_MODIFIED = "pending", "accepted", "rejected", "modified"


class Proposal(AuditedBase):
    __tablename__ = "proposals"
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=P_PENDING_REVIEW)
    proposed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    # 반영 대상 맥락 — 템플릿 연결 제안은 템플릿 판과, 승인 후 다시 불러올 스코핑
    template_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scoping_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # 반영 결과 요약


class ProposalItem(AuditedBase):
    __tablename__ = "proposal_items"
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("proposals.id"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 대상 — 재무제표 계정(이름은 제안 당시 표기를 남긴다: 계정이 바뀌어도 무엇을 제안했는지 보이게)
    account_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    statement_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, default=ITEM_LINK)
    template_account_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # 1차 결정
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default=D_PENDING)
    decided_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_template_account_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    final_template_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
