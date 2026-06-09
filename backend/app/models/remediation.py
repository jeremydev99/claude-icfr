from datetime import date, datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class Deficiency(AuditedBase):
    __tablename__ = "deficiencies"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    test_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_runs.id"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    # Phase 1 확장 — 연도 + 통제 연결
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2025, index=True)
    control_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=True, index=True
    )

    # Phase 1 확장 — 결론
    final_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    remediation_plan: Mapped["RemediationPlan | None"] = relationship(
        "RemediationPlan", back_populates="deficiency", uselist=False
    )
    control: Mapped["Control | None"] = relationship("Control", foreign_keys="[Deficiency.control_id]")


class RemediationPlan(AuditedBase):
    __tablename__ = "remediation_plans"

    deficiency_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("deficiencies.id"), nullable=False, unique=True, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_plan: Mapped[str] = mapped_column(Text, nullable=False)

    # Phase 1 확장 — 워크플로 4단계
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", index=True)

    # Phase 1 확장 — 개선 정보 (양식 그룹 8 BW~CA)
    improvement_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="Medium")
    owner_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 승인 추적
    approved_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deficiency: Mapped["Deficiency"] = relationship("Deficiency", back_populates="remediation_plan")
    status_history: Mapped[list["RemediationStatusHistory"]] = relationship(
        "RemediationStatusHistory", back_populates="plan", cascade="all, delete-orphan"
    )


class DesignAssessment(AuditedBase):
    """설계평가 — 한 통제·한 연도 = 1건 (사이냅소프트 양식 BG~BV)."""
    __tablename__ = "design_assessments"

    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # 8요소 점수 (1=미흡, 2=보통, 3=우수)
    design_score_1: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_2: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_3: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_4: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_5: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_6: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_7: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    design_score_8: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # 종합 판정 (BN)
    overall_design: Mapped[str] = mapped_column(String(20), nullable=False, default="Effective")
    design_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 평가방법·통제수행자 (BP~BV)
    assessment_method: Mapped[str] = mapped_column(String(20), nullable=False, default="Walkthrough")
    performer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    performance_frequency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 평가자
    assessor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    control: Mapped["Control"] = relationship("Control", foreign_keys="[DesignAssessment.control_id]")

    __table_args__ = (
        UniqueConstraint("control_id", "fiscal_year", name="uq_design_assessment_control_year"),
    )


class RemediationStatusHistory(AuditedBase):
    """RemediationPlan 상태 변경 이력 — TestStatusHistory 스타일 (작업3)."""
    __tablename__ = "remediation_status_history"

    remediation_plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("remediation_plans.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["RemediationPlan"] = relationship("RemediationPlan", back_populates="status_history", foreign_keys="[RemediationStatusHistory.remediation_plan_id]")
    changed_by: Mapped["User"] = relationship("User", foreign_keys="[RemediationStatusHistory.changed_by_id]")
