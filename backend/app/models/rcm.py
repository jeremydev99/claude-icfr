from uuid import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import AuditedBase


class Process(AuditedBase):
    __tablename__ = "processes"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    sub_processes: Mapped[list["SubProcess"]] = relationship("SubProcess", back_populates="process")


class SubProcess(AuditedBase):
    """하위프로세스. 예: EL-010 (통제환경), SD-010 (주문 및 거래관리)."""
    __tablename__ = "sub_processes"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    process_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("processes.id"), nullable=False, index=True
    )

    process: Mapped["Process"] = relationship("Process", back_populates="sub_processes")
    risks: Mapped[list["Risk"]] = relationship("Risk", back_populates="sub_process")


class Risk(AuditedBase):
    """위험. K-ICFR 표준 — SubProcess에 1:N. 예: EL-010-10."""
    __tablename__ = "risks"

    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_level: Mapped[str] = mapped_column(String(5), nullable=False, default="LR")
    # "LR" (Low), "MR" (Medium), "HR" (High), "SR" (Significant)
    sub_process_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sub_processes.id"), nullable=False, index=True
    )

    sub_process: Mapped["SubProcess"] = relationship("SubProcess", back_populates="risks")
    controls: Mapped[list["Control"]] = relationship("Control", back_populates="risk")


class RiskCategory(AuditedBase):
    """경영자 주장 분류 (Assertion). 예: E (Existence), C (Completeness)."""
    __tablename__ = "risk_categories"

    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Control(AuditedBase):
    """통제 활동. Risk를 통해 Process 체인 추적. 예: EL-010-10-10."""
    __tablename__ = "controls"

    # 기본 식별자
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("risks.id"), nullable=False, index=True
    )

    # 그룹 2: 담당자·목적
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 그룹 3: 통제 성격
    is_key_control: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preventive_detective: Mapped[str] = mapped_column(String(2), nullable=False, default="P")
    # "P" (Preventive), "D" (Detective)
    auto_manual: Mapped[str] = mapped_column(String(2), nullable=False, default="M")
    # "A" (Automated), "M" (Manual), "IT" (IT-Dependent Manual)

    # 그룹 3: 통제 활동 유형 6종 (Boolean 플래그 — ADR-0020 원칙: 추상화 금지)
    activity_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_physical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_master_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_reconciliation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_supervision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 그룹 5: 통제 환경·시스템
    related_accounts: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(String(2), nullable=False, default="A")
    # "O" (Occasional), "D" (Daily), "W" (Weekly), "M" (Monthly), "Q" (Quarterly), "A" (Annual)
    ipe_relevant: Mapped[str] = mapped_column(String(5), nullable=False, default="N/A")
    # "Y", "N", "N/A"
    related_systems: Mapped[str | None] = mapped_column(Text, nullable=True)
    euc_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    risk: Mapped["Risk"] = relationship("Risk", back_populates="controls")
    assertions: Mapped[list["ControlAssertion"]] = relationship(
        "ControlAssertion", back_populates="control", cascade="all, delete-orphan"
    )


class ControlAssertion(AuditedBase):
    """통제와 경영자 주장(Assertion)의 N:M 매핑."""
    __tablename__ = "control_assertions"

    control_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("controls.id"), nullable=False, index=True
    )
    risk_category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("risk_categories.id"), nullable=False, index=True
    )

    control: Mapped["Control"] = relationship("Control", back_populates="assertions")
    risk_category: Mapped["RiskCategory"] = relationship("RiskCategory")
