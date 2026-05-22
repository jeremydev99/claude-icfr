from datetime import date, datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Boolean, Date, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class ControlRiskAssessment(AuditedBase):
    """RAWC 평가 — 한 통제 × 한 연도 = 1건. 사이냅소프트 양식 그룹 6 (AN~AV)."""
    __tablename__ = "control_risk_assessments"

    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # 7가지 평가 요소 (AN~AT, 각 1~3점)
    frequency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    nature_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    precision_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    dependency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    automation_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    authority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    review_score: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # 과거 효과성 (AU)
    prior_year_effectiveness: Mapped[str] = mapped_column(String(20), nullable=False, default="N/A")
    # "Effective", "Not_Effective", "N/A"

    # 종합 판정 (AV)
    overall_assessment: Mapped[str] = mapped_column(String(20), nullable=False, default="Not_Higher")
    # "Not_Higher", "Higher"

    assessor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("control_id", "fiscal_year", name="uq_rawc_control_year"),
    )


class TestRun(AuditedBase):
    """통제 평가 실행. 연도별 1건 (fiscal_year). 4단계 워크플로 (ADR-0020: String 컬럼 + dict)."""
    __tablename__ = "test_runs"

    # 기존 (작업6 → nullable로 완화)
    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    tester_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    test_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "pass", "fail", "n/a"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 신규: 연도 + 워크플로 상태
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", index=True)
    # "planned", "in_progress", "completed", "approved"

    # 신규: 그룹 7 (AW~BF)
    wtt_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    existing_process_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    method_inquiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    method_observation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    method_inspection: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    method_reperformance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    population: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_frequency: Mapped[str | None] = mapped_column(String(2), nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    procedure: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 신규: 승인 정보
    approved_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="test_run", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["TestStatusHistory"]] = relationship(
        "TestStatusHistory", back_populates="test_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("control_id", "fiscal_year", name="uq_testrun_control_year"),
    )


class TestStep(AuditedBase):
    """평가 절차의 한 스텝. 변경 없음 (작업6 유지)."""
    __tablename__ = "test_steps"

    test_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_runs.id"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)

    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="steps")


class TestStatusHistory(AuditedBase):
    """TestRun 상태 변경 이력 — 추가 전용. ICFR 제도의 추적성·증거성 충족."""
    __tablename__ = "test_status_history"

    test_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_runs.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 최초 생성 시 NULL
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="status_history")
    changed_by: Mapped["User"] = relationship("User", foreign_keys=[changed_by_id])
