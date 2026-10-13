"""AI 제안 기록 (ADR-0042) — 제안 원문·근거·계기·엔진과 채택자를 남긴다.

책임 주체는 채택한 사람이다. 제안 행의 `created_by` 는 `system:ai`.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditedBase

AI_PROPOSED, AI_ADOPTED, AI_DISCARDED, AI_SUPERSEDED = "proposed", "adopted", "discarded", "superseded"
AI_STATUS_LABELS = {AI_PROPOSED: "제안", AI_ADOPTED: "채택", AI_DISCARDED: "폐기", AI_SUPERSEDED: "대체됨"}

KIND_SCHEDULE_PLAN = "schedule_plan"
KIND_LABELS = {KIND_SCHEDULE_PLAN: "연간 일정안"}


class AiProposal(AuditedBase):
    __tablename__ = "ai_proposals"
    __table_args__ = (
        Index("ix_ai_proposals_target", "target_type", "target_id"),
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AI_PROPOSED)
    engine: Mapped[str] = mapped_column(String(80), nullable=False)          # rule:<이름> | claude:<모델>
    trigger: Mapped[str] = mapped_column(Text, nullable=False)              # 언제·왜 제안했나(사람이 읽는 문장)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    basis: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # 무엇을 보고 — 출처·조정 내역
    proposed: Mapped[list | dict] = mapped_column(JSON, nullable=False, default=dict)  # 제안 원문 사본
    adopted_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    adopted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    adopted_changes: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 채택 시 원문 대비 바뀐 것
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

